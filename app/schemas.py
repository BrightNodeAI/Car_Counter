from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


class JobStatus(BaseModel):
    id: str
    status: Literal["queued", "processing", "complete", "cancelled", "failed"]
    progress: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    in_count: int = 0
    out_count: int = 0
    class_counts: dict[str, int] = {}
    fps: Optional[float] = None
    error: Optional[str] = None
    filename: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    has_video: bool = False
    has_csv: bool = False


class LiveStartRequest(BaseModel):
    source_type: Literal["webcam", "rtsp"]
    source_value: str = "0"
    conf: float = 0.4
    line_axis: Literal["horizontal", "vertical"] = "horizontal"
    line_length: float = 1.0
    imgsz: int = 640


class LiveStartResponse(BaseModel):
    session_id: str


class LiveStatus(BaseModel):
    id: str
    status: Literal["running", "stopped", "error"]
    in_count: int = 0
    out_count: int = 0
    n_dets: int = 0
    is_recording: bool = False
    error: Optional[str] = None
