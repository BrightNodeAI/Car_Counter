"""
main.py — FastAPI app for the Bright Node Car Counter.

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles as _StaticFiles

from .jobs import job_manager, UPLOAD_DIR
from .live import live_manager
from .schemas import JobStatus, LiveStartRequest, LiveStartResponse, LiveStatus

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


class StaticFiles(_StaticFiles):
    """Static file server that disables browser caching.

    This app is actively developed locally — without this, editing
    static/app.js or static/index.html and restarting uvicorn can still
    serve a stale cached copy until the person does a hard refresh.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app = FastAPI(title="Bright Node — Car Counter")

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMGSZ = {320, 480, 640}


def _job_to_status(job) -> JobStatus:
    return JobStatus(
        id=job.id,
        status=job.status,
        progress=job.progress,
        total_frames=job.total_frames,
        processed_frames=job.processed_frames,
        in_count=job.in_count,
        out_count=job.out_count,
        class_counts=job.class_counts,
        fps=job.fps,
        error=job.error,
        filename=job.filename,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        duration_seconds=job.duration_seconds,
        has_video=job.output_video_path is not None and job.output_video_path.exists(),
        has_csv=job.output_csv_path is not None and job.output_csv_path.exists(),
    )


# ── Upload & batch processing ──────────────────────────────────────────────
@app.post("/api/jobs", response_model=JobStatus)
async def create_job(
    file: UploadFile = File(...),
    conf: float = Form(0.4),
    line_axis: str = Form("horizontal"),
    line_length: float = Form(1.0),
    imgsz: int = Form(640),
    max_duration: float | None = Form(None),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use one of {sorted(ALLOWED_VIDEO_EXT)}.")
    if line_axis not in ("horizontal", "vertical"):
        raise HTTPException(400, "line_axis must be 'horizontal' or 'vertical'.")
    if not (0.05 <= conf <= 0.95):
        raise HTTPException(400, "conf must be between 0.05 and 0.95.")
    if not (0.1 <= line_length <= 1.0):
        raise HTTPException(400, "line_length must be between 0.1 and 1.0.")
    if imgsz not in ALLOWED_IMGSZ:
        raise HTTPException(400, f"imgsz must be one of {sorted(ALLOWED_IMGSZ)}.")
    if max_duration is not None and max_duration <= 0:
        max_duration = None

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:12]}{ext}"
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    job = job_manager.create_job(dest, file.filename or dest.name, conf, line_axis,
                                  line_length=line_length, imgsz=imgsz,
                                  max_duration=max_duration)
    return _job_to_status(job)


@app.get("/api/jobs", response_model=list[JobStatus])
async def list_jobs():
    return [_job_to_status(j) for j in job_manager.list_jobs()]


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return _job_to_status(job)


@app.get("/api/jobs/{job_id}/video")
async def get_job_video(job_id: str):
    job = job_manager.get(job_id)
    if not job or not job.output_video_path or not job.output_video_path.exists():
        raise HTTPException(404, "Video not ready yet.")
    return FileResponse(job.output_video_path, media_type="video/mp4", filename=f"{job.id}_annotated.mp4")


@app.get("/api/jobs/{job_id}/preview")
async def job_preview(job_id: str):
    """MJPEG stream of the annotated frame currently being processed.

    Only meaningful while the job is queued/processing; the stream closes
    itself once the job finishes so the frontend can switch to the final
    output video.
    """
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    def gen():
        boundary = b"--frame\r\n"
        while job.status in ("queued", "processing"):
            jpg = job.get_latest_jpeg()
            if jpg is not None:
                yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.04)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/jobs/{job_id}/csv")
async def get_job_csv(job_id: str):
    job = job_manager.get(job_id)
    if not job or not job.output_csv_path or not job.output_csv_path.exists():
        raise HTTPException(404, "Log not ready yet.")
    return FileResponse(job.output_csv_path, media_type="text/csv", filename=f"{job.id}_log.csv")


@app.post("/api/jobs/{job_id}/stop", response_model=JobStatus)
async def stop_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status not in ("queued", "processing"):
        raise HTTPException(400, f"Job is already {job.status}.")
    job_manager.request_cancel(job_id)
    return _job_to_status(job)


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    deleted = job_manager.delete_job(job_id)
    if not deleted:
        raise HTTPException(404, "Job not found.")
    return {"deleted": True, "id": job_id}


# ── Live sessions (webcam / RTSP) ──────────────────────────────────────────
@app.post("/api/live/start", response_model=LiveStartResponse)
async def live_start(req: LiveStartRequest):
    if req.source_type == "webcam":
        if not req.source_value.strip().isdigit():
            raise HTTPException(400, "Webcam source must be a device index, e.g. 0.")
    elif not req.source_value.strip():
        raise HTTPException(400, "RTSP source URL is required.")
    if not (0.1 <= req.line_length <= 1.0):
        raise HTTPException(400, "line_length must be between 0.1 and 1.0.")
    if req.imgsz not in ALLOWED_IMGSZ:
        raise HTTPException(400, f"imgsz must be one of {sorted(ALLOWED_IMGSZ)}.")

    session = live_manager.start(req.source_type, req.source_value.strip(), req.conf,
                                  req.line_axis, req.line_length, req.imgsz)

    # give the capture thread a brief moment to fail fast on a bad source
    for _ in range(20):
        if session.status in ("running", "error"):
            break
        time.sleep(0.1)
    if session.status == "error":
        raise HTTPException(400, session.error or "Could not start the live source.")

    return LiveStartResponse(session_id=session.id)


@app.get("/api/live/{session_id}/status", response_model=LiveStatus)
async def live_status(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Live session not found.")
    return LiveStatus(
        id=session.id, status=session.status, in_count=session.in_count,
        out_count=session.out_count, n_dets=session.n_dets,
        is_recording=session.is_recording, error=session.error,
    )


@app.get("/api/live/{session_id}/feed")
async def live_feed(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Live session not found.")

    def gen():
        boundary = b"--frame\r\n"
        while session.status in ("running", "starting"):
            jpg = session.latest_jpeg()
            if jpg is not None:
                yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.03)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/live/{session_id}/record", response_model=LiveStatus)
async def live_toggle_record(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Live session not found.")
    session.toggle_record()
    return LiveStatus(
        id=session.id, status=session.status, in_count=session.in_count,
        out_count=session.out_count, n_dets=session.n_dets,
        is_recording=session.is_recording, error=session.error,
    )


@app.post("/api/live/{session_id}/stop", response_model=LiveStatus)
async def live_stop(session_id: str):
    session = live_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Live session not found.")
    live_manager.stop(session_id)
    return LiveStatus(
        id=session.id, status="stopped", in_count=session.in_count,
        out_count=session.out_count, n_dets=session.n_dets,
        is_recording=session.is_recording, error=session.error,
    )


# ── Static frontend ─────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )
