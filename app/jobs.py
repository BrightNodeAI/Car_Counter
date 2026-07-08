"""
jobs.py — Manages batch processing of uploaded videos in background threads.

Each job runs the CarCounterPipeline over every frame of an uploaded video,
writes an annotated output video + a CSV crossing log, and exposes progress
so the frontend can poll for status.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from .pipeline import CarCounterPipeline

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Codecs tried in order — 'avc1'/H264 plays natively in <video>, mp4v is the
# safe OpenCV fallback but some browsers won't preview it inline.
_CODEC_CANDIDATES = ["avc1", "H264", "mp4v"]


@dataclass
class Job:
    id: str
    filename: str
    conf: float
    line_axis: str
    line_length: float = 1.0
    imgsz: int = 640                         # inference resolution (320/480/640)
    max_duration: Optional[float] = None     # seconds; None/0 = process full video
    status: str = "queued"          # queued | processing | complete | cancelled | failed
    progress: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    in_count: int = 0
    out_count: int = 0
    class_counts: dict = field(default_factory=dict)
    fps: Optional[float] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    video_path: Optional[Path] = None
    output_video_path: Optional[Path] = None
    output_csv_path: Optional[Path] = None
    codec_used: Optional[str] = None
    latest_jpeg: Optional[bytes] = field(default=None, repr=False)
    frame_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self.frame_lock:
            return self.latest_jpeg

    def _set_latest_jpeg(self, data: bytes) -> None:
        with self.frame_lock:
            self.latest_jpeg = data


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, upload_path: Path, filename: str, conf: float, line_axis: str,
                   line_length: float = 1.0, imgsz: int = 640,
                   max_duration: Optional[float] = None) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, filename=filename, conf=conf, line_axis=line_axis,
                  line_length=line_length, imgsz=imgsz, max_duration=max_duration,
                  video_path=upload_path)
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def request_cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.status not in ("queued", "processing"):
            return False
        job.cancel_event.set()
        return True

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job.status in ("queued", "processing"):
                job.cancel_event.set()
            self._jobs.pop(job_id, None)

        for path in [job.video_path, job.output_video_path, job.output_csv_path]:
            if path:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

        if job.id:
            for candidate in [OUTPUT_DIR / f"{job.id}.mp4", OUTPUT_DIR / f"{job.id}_h264.mp4", OUTPUT_DIR / f"{job.id}.csv"]:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass

        return True

    # -- worker -----------------------------------------------------------
    def _open_writer(self, path: Path, fps: float, size: tuple[int, int]) -> tuple[Optional[cv2.VideoWriter], Optional[str]]:
        for codec in _CODEC_CANDIDATES:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(str(path), fourcc, fps, size)
            if writer.isOpened():
                return writer, codec
            writer.release()
        return None, None

    def _run(self, job: Job) -> None:
        job.status = "processing"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        try:
            cap = cv2.VideoCapture(str(job.video_path))
            if not cap.isOpened():
                raise RuntimeError("Could not open uploaded video — is it a supported format?")

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            job.fps = fps

            frame_limit = total if total > 0 else None
            if job.max_duration and job.max_duration > 0:
                requested_frames = int(round(job.max_duration * fps))
                frame_limit = min(frame_limit, requested_frames) if frame_limit else requested_frames
            job.total_frames = frame_limit or 0

            out_path = OUTPUT_DIR / f"{job.id}.mp4"
            writer, codec = self._open_writer(out_path, fps, (w, h))
            if writer is None:
                raise RuntimeError("No usable video codec found on this server (tried avc1/H264/mp4v).")
            job.codec_used = codec

            weights = os.environ.get("CAR_COUNTER_WEIGHTS", "yolov8n.pt")
            pipeline = CarCounterPipeline(conf=job.conf, line_axis=job.line_axis,
                                           line_length_frac=job.line_length,
                                           imgsz=job.imgsz, weights=weights)
            pipeline.setup(w, h)

            log_rows = []
            frame_idx = 0
            while True:
                if frame_limit and frame_idx >= frame_limit:
                    break
                if job.cancel_event.is_set():
                    break
                ret, frame = cap.read()
                if not ret:
                    break
                frame_idx += 1
                annotated, info = pipeline.process(frame, frame_idx)
                writer.write(annotated)

                ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 78])
                if ok:
                    job._set_latest_jpeg(buf.tobytes())

                log_rows.append({
                    "frame": frame_idx,
                    "in": info["in_count"],
                    "out": info["out_count"],
                    "in_frame": info["n_dets"],
                })
                job.processed_frames = frame_idx
                job.in_count = info["in_count"]
                job.out_count = info["out_count"]
                job.class_counts = info["class_counts"]
                job.progress = min(frame_idx / job.total_frames, 1.0) if job.total_frames else 0.0

            cap.release()
            writer.release()

            csv_path = OUTPUT_DIR / f"{job.id}.csv"
            if log_rows:
                with open(csv_path, "w", newline="") as f:
                    wr = csv.DictWriter(f, fieldnames=log_rows[0].keys())
                    wr.writeheader()
                    wr.writerows(log_rows)
                job.output_csv_path = csv_path

            if frame_idx == 0:
                # nothing was ever written — drop the empty stub file
                out_path.unlink(missing_ok=True)
            else:
                # Best-effort transcode to H.264 for guaranteed browser playback,
                # if ffmpeg happens to be installed. Falls back silently otherwise.
                if codec != "avc1" and shutil.which("ffmpeg"):
                    h264_path = OUTPUT_DIR / f"{job.id}_h264.mp4"
                    try:
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(out_path), "-c:v", "libx264",
                             "-preset", "veryfast", "-pix_fmt", "yuv420p", str(h264_path)],
                            check=True, capture_output=True, timeout=600,
                        )
                        out_path.unlink(missing_ok=True)
                        h264_path.rename(out_path)
                    except Exception:
                        pass  # keep the original file; still downloadable
                job.output_video_path = out_path

            if job.cancel_event.is_set():
                job.status = "cancelled"
            else:
                job.progress = 1.0
                job.status = "complete"
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)
        finally:
            finished = datetime.now()
            job.finished_at = finished.isoformat(timespec="seconds")
            if job.started_at:
                job.duration_seconds = (finished - datetime.fromisoformat(job.started_at)).total_seconds()


job_manager = JobManager()
