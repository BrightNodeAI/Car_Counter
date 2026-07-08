"""
pipeline.py — Headless YOLOv8 + ByteTrack car counting pipeline.

Refactored from the original CarCounterYOLO.py CLI script so it can be
driven frame-by-frame by a FastAPI server (batch jobs and live sessions)
instead of a local OpenCV GUI window.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv

BRAND = "BrightNode"
TAGLINE = "DATA - VISION - PYTHON"
COCO_CLASSES = {"car", "truck", "bus", "motorcycle"}

# Default watermark logo: a BrightNodeLogo.jpg sitting next to this file,
# overridable via the CAR_COUNTER_LOGO env var (same pattern as the weights).
_DEFAULT_LOGO = Path(__file__).resolve().parent / "BrightNodeLogo.jpg"


def default_logo_path() -> Optional[str]:
    env = os.environ.get("CAR_COUNTER_LOGO")
    if env:
        return env
    return str(_DEFAULT_LOGO) if _DEFAULT_LOGO.exists() else None

# Model loading is expensive (weights download / device placement) — do it
# once per process and share the same weights across jobs and live sessions.
_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, YOLO] = {}


def _resolve_weights(weights: str) -> str:
    """Prefer an OpenVINO export ('<stem>_openvino_model' directory next to
    the .pt file) when present — 2-3x faster than PyTorch on Intel CPUs,
    identical detections. Create one with:
        YOLO('yolov8n.pt').export(format='openvino', dynamic=True)
    """
    p = Path(weights)
    ov_dir = p.with_name(p.stem + "_openvino_model")
    if ov_dir.is_dir():
        return str(ov_dir)
    return weights


def get_model(weights: str = "yolov8n.pt") -> YOLO:
    resolved = _resolve_weights(weights)
    with _MODEL_LOCK:
        if resolved not in _MODEL_CACHE:
            _MODEL_CACHE[resolved] = YOLO(resolved)
        return _MODEL_CACHE[resolved]


def load_logo(path: Optional[str], size: int) -> Optional[np.ndarray]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    logo = cv2.imread(str(p))
    if logo is None:
        return None
    return cv2.resize(logo, (size, size), interpolation=cv2.INTER_AREA)


def stamp_watermark(frame: np.ndarray, logo: Optional[np.ndarray]) -> np.ndarray:
    """Stamp Bright Node logo + text at bottom-right (unchanged from CLI tool)."""
    h, w = frame.shape[:2]
    margin, pad, txt_gap = 12, 8, 6
    logo_size = 64

    font = cv2.FONT_HERSHEY_DUPLEX
    font_small = cv2.FONT_HERSHEY_SIMPLEX
    (bw, bh), _ = cv2.getTextSize(BRAND, font, 0.62, 2)
    (tw, th), _ = cv2.getTextSize(TAGLINE, font_small, 0.34, 1)

    logo_h = logo_size if logo is not None else 0
    logo_w = logo_size if logo is not None else 0

    text_block_w = max(bw, tw)
    text_block_h = bh + 6 + th

    pill_w = pad + logo_w + (txt_gap if logo is not None else 0) + text_block_w + pad
    pill_h = pad + max(logo_h, text_block_h) + pad

    x0, y0 = w - pill_w - margin, h - pill_h - margin
    x1, y1 = w - margin, h - margin

    overlay = frame.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    if logo is not None:
        lx = x0 + pad
        ly = y0 + pad + (max(logo_h, text_block_h) - logo_h) // 2
        roi = frame[ly:ly + logo_size, lx:lx + logo_size]
        if roi.shape[:2] == (logo_size, logo_size):
            mask = cv2.cvtColor(logo, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(mask, 230, 255, cv2.THRESH_BINARY)
            logo_fg = cv2.bitwise_and(logo, logo, mask=cv2.bitwise_not(mask))
            roi_bg = cv2.bitwise_and(roi, roi, mask=mask)
            frame[ly:ly + logo_size, lx:lx + logo_size] = cv2.add(logo_fg, roi_bg)

    tx = x0 + pad + logo_w + (txt_gap if logo is not None else 0)
    ty_brand = y0 + pad + (max(logo_h, text_block_h) - text_block_h) // 2 + bh
    ty_tagline = ty_brand + 6 + th

    (bright_w, _), _ = cv2.getTextSize("Bright", font, 0.62, 2)
    cv2.putText(frame, "Bright", (tx, ty_brand), font, 0.62, (255, 255, 255), 2)
    cv2.putText(frame, "Node", (tx + bright_w, ty_brand), font, 0.62, (50, 190, 255), 2)
    cv2.putText(frame, TAGLINE, (tx, ty_tagline), font_small, 0.34, (180, 180, 180), 1)
    return frame


def draw_hud(frame: np.ndarray, in_count: int, out_count: int,
             n_dets: int, is_recording: bool, frame_idx: int) -> np.ndarray:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (200, 95), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
    cv2.putText(frame, f"IN : {in_count}", (20, 45), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 230, 80), 2)
    cv2.putText(frame, f"OUT: {out_count}", (20, 85), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 100, 255), 2)

    label = f"Cars in frame: {n_dets}"
    cv2.putText(frame, label, (w - 270, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (220, 220, 220), 2)

    if is_recording and (frame_idx // 15) % 2 == 0:
        rec_text = "  REC"
        (rw, _), _ = cv2.getTextSize(rec_text, cv2.FONT_HERSHEY_DUPLEX, 0.85, 2)
        rx = (w - rw) // 2
        cv2.circle(frame, (rx - 10, 28), 9, (0, 0, 220), -1)
        cv2.putText(frame, rec_text, (rx, 38), cv2.FONT_HERSHEY_DUPLEX, 0.85, (0, 0, 220), 2)

    return frame


def build_line(w: int, h: int, axis: str, length_frac: float = 1.0) -> sv.LineZone:
    """Build a counting line centered on the frame.

    length_frac controls how much of the frame the line spans (1.0 = edge
    to edge, 0.1 = a short segment centered on the frame) so a line can be
    narrowed to a single lane instead of the whole road width.
    """
    length_frac = max(0.1, min(1.0, length_frac))
    if axis == "vertical":
        span = h * length_frac
        y0 = int((h - span) / 2)
        y1 = int(y0 + span)
        x = int(w * 0.5)
        return sv.LineZone(start=sv.Point(x, y0), end=sv.Point(x, y1))

    span = w * length_frac
    x0 = int((w - span) / 2)
    x1 = int(x0 + span)
    y = int(h * 0.5)
    return sv.LineZone(start=sv.Point(x0, y), end=sv.Point(x1, y))


class CarCounterPipeline:
    """Stateful per-video pipeline: one instance per job / live session."""

    def __init__(self, conf: float = 0.4, line_axis: str = "horizontal",
                 line_length_frac: float = 1.0, imgsz: int = 640,
                 weights: str = "yolov8n.pt", logo_path: Optional[str] = None,
                 draw_watermark: bool = True):
        self.conf = conf
        self.line_axis = line_axis
        self.line_length_frac = line_length_frac
        self.imgsz = imgsz
        self.model = get_model(weights)
        self.logo = load_logo(logo_path or default_logo_path(), 64)
        self.draw_watermark = draw_watermark

        self.tracker = sv.ByteTrack()
        self.line_zone: Optional[sv.LineZone] = None
        self.line_ann = sv.LineZoneAnnotator(thickness=3, text_scale=1.0)
        self.box_ann = sv.BoxAnnotator(thickness=2)
        self.label_ann = sv.LabelAnnotator(text_scale=0.5, text_padding=4)

        self.target_ids = [k for k, v in self.model.names.items() if v in COCO_CLASSES]
        self.class_counts: dict[str, int] = {name: 0 for name in COCO_CLASSES}
        self._ready = False

    def setup(self, width: int, height: int) -> None:
        self.line_zone = build_line(width, height, self.line_axis, self.line_length_frac)
        self._ready = True

    @property
    def in_count(self) -> int:
        return self.line_zone.in_count if self.line_zone else 0

    @property
    def out_count(self) -> int:
        return self.line_zone.out_count if self.line_zone else 0

    @property
    def class_breakdown(self) -> dict[str, int]:
        return dict(self.class_counts)

    def process(self, frame: np.ndarray, frame_idx: int, is_recording: bool = False) -> tuple[np.ndarray, dict]:
        if not self._ready:
            h, w = frame.shape[:2]
            self.setup(w, h)

        results = self.model(frame, verbose=False, conf=self.conf, imgsz=self.imgsz)[0]
        dets = sv.Detections.from_ultralytics(results)

        if self.target_ids:
            dets = dets[np.isin(dets.class_id, self.target_ids)]

        dets = self.tracker.update_with_detections(dets)
        crossed_in, crossed_out = self.line_zone.trigger(detections=dets)
        for cid, cin, cout in zip(dets.class_id, crossed_in, crossed_out):
            if cin or cout:
                name = self.model.names[cid]
                self.class_counts[name] = self.class_counts.get(name, 0) + 1

        labels = [
            f"{self.model.names[c]}  {cf:.2f}"
            for c, cf in zip(dets.class_id, dets.confidence)
        ] if len(dets) else []

        frame = self.box_ann.annotate(scene=frame, detections=dets)
        frame = self.label_ann.annotate(scene=frame, detections=dets, labels=labels)
        frame = self.line_ann.annotate(frame, line_counter=self.line_zone)
        frame = draw_hud(frame, self.in_count, self.out_count, len(dets), is_recording, frame_idx)
        if self.draw_watermark:
            frame = stamp_watermark(frame, self.logo)

        info = {
            "in_count": self.in_count,
            "out_count": self.out_count,
            "n_dets": len(dets),
            "class_counts": self.class_breakdown,
        }
        return frame, info
