"""
live.py — Manages live camera / RTSP sessions.

Since the app runs locally with uvicorn, "webcam" means a camera attached to
the machine running the server (cv2.VideoCapture(index)). RTSP sources are
opened directly by OpenCV as well. Each session runs its own capture/inference
loop in a background thread and exposes the latest annotated JPEG frame for
an MJPEG stream, plus optional recording to disk.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from .pipeline import CarCounterPipeline

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

_CODEC_CANDIDATES = ["avc1", "H264", "mp4v"]


class LiveSession:
    def __init__(self, session_id: str, source, conf: float, line_axis: str,
                 line_length: float = 1.0, imgsz: int = 640):
        self.id = session_id
        self.source = source
        self.conf = conf
        self.line_axis = line_axis
        self.line_length = line_length
        self.imgsz = imgsz

        self.status = "starting"   # starting | running | stopped | error
        self.error: Optional[str] = None
        self.in_count = 0
        self.out_count = 0
        self.n_dets = 0
        self.is_recording = False

        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._stop_event = threading.Event()
        self._rec_writer: Optional[cv2.VideoWriter] = None
        self._rec_path: Optional[Path] = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.status = "error"
            self.error = f"Could not open source: {self.source}"
            return

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._fps = fps if fps > 1 else 25.0
        self._size = (w, h)

        weights = os.environ.get("CAR_COUNTER_WEIGHTS", "yolov8n.pt")
        pipeline = CarCounterPipeline(conf=self.conf, line_axis=self.line_axis,
                                       line_length_frac=self.line_length,
                                       imgsz=self.imgsz, weights=weights)
        pipeline.setup(w, h)
        self.status = "running"
        frame_idx = 0

        try:
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    # RTSP hiccup or webcam disconnect — brief retry, then give up
                    time.sleep(0.5)
                    ret, frame = cap.read()
                    if not ret:
                        self.status = "error"
                        self.error = "Lost connection to the video source."
                        break

                frame_idx += 1
                annotated, info = pipeline.process(frame, frame_idx, is_recording=self.is_recording)

                ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    with self._lock:
                        self._latest_jpeg = buf.tobytes()

                self.in_count = info["in_count"]
                self.out_count = info["out_count"]
                self.n_dets = info["n_dets"]

                with self._lock:
                    if self._rec_writer is not None:
                        self._rec_writer.write(annotated)
        finally:
            cap.release()
            with self._lock:
                if self._rec_writer is not None:
                    self._rec_writer.release()
                    self._rec_writer = None
            if self.status == "running":
                self.status = "stopped"

    def latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def stop(self) -> None:
        self._stop_event.set()

    def toggle_record(self) -> bool:
        with self._lock:
            if self._rec_writer is None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = OUTPUT_DIR / f"live_{self.id}_{ts}.mp4"
                writer = None
                for codec in _CODEC_CANDIDATES:
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    w = cv2.VideoWriter(str(path), fourcc, self._fps, self._size)
                    if w.isOpened():
                        writer = w
                        break
                    w.release()
                if writer is None:
                    return self.is_recording
                self._rec_writer = writer
                self._rec_path = path
                self.is_recording = True
            else:
                self._rec_writer.release()
                self._rec_writer = None
                self.is_recording = False
        return self.is_recording


class LiveManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._lock = threading.Lock()

    def start(self, source_type: str, source_value: str, conf: float, line_axis: str,
              line_length: float = 1.0, imgsz: int = 640) -> LiveSession:
        source = int(source_value) if source_type == "webcam" else source_value
        session_id = uuid.uuid4().hex[:12]
        session = LiveSession(session_id, source, conf, line_axis, line_length, imgsz)
        with self._lock:
            self._sessions[session_id] = session
        session.start()
        return session

    def get(self, session_id: str) -> Optional[LiveSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def stop(self, session_id: str) -> None:
        session = self.get(session_id)
        if session:
            session.stop()


live_manager = LiveManager()
