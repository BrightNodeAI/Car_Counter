# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000. Dependencies are managed with uv: `uv sync` creates the
repo-local `.venv/` from `pyproject.toml`/`uv.lock` (Python 3.12 via `.python-version`,
CPU-only torch from the pytorch.org index). `.claude/launch.json` points at
`.venv\Scripts\uvicorn.exe`, so `preview_start` with the `car-counter` config also works.

There are no tests or lint configuration.

Environment variables (read by both jobs and live sessions):
- `CAR_COUNTER_WEIGHTS` — path to alternate YOLO `.pt` weights (default `yolov8n.pt`)
- `CAR_COUNTER_LOGO` — path to the watermark logo image

## Architecture

Two workflows share one inference core:

1. **Upload & Process** (`app/jobs.py`) — a video is uploaded via `POST /api/jobs`,
   then processed frame-by-frame in a background `threading.Thread`. Produces an
   annotated MP4 + CSV crossing log in `outputs/`, with progress polled by the frontend.
2. **Live Feed** (`app/live.py`) — webcam (device index) or RTSP URL, opened by OpenCV
   on the server (not the browser's camera). Each session runs its own capture/inference
   thread and supports toggling recording to disk.

Shared pieces:

- `app/pipeline.py` — `CarCounterPipeline`, the headless detection/tracking/counting core
  (refactored from an earlier `CarCounterYOLO.py` CLI script). One stateful instance per
  job/session. YOLO models are cached process-wide (`get_model`), and an OpenVINO export
  directory (`<stem>_openvino_model/` next to the `.pt`) is auto-preferred over PyTorch
  weights when present — `yolov8n_openvino_model/` exists in the repo root for this reason.
  Counts only COCO classes car/truck/bus/motorcycle via a `supervision` `LineZone`.
- `app/main.py` — all routes. Also subclasses `StaticFiles` to disable browser caching of
  `static/` (deliberate: local dev without hard refreshes). Keep that behavior.
- `app/schemas.py` — Pydantic request/response models; route handlers convert `Job` /
  `LiveSession` objects to these.
- `static/` — vanilla HTML/CSS/JS frontend (no build step, no framework). Talks to the
  API via `fetch` polling; video previews use MJPEG (`multipart/x-mixed-replace`) streams
  from `/api/jobs/{id}/preview` and `/api/live/{id}/feed`.

Things that aren't obvious from any single file:

- **All state is in-memory.** `job_manager` and `live_manager` are module-level singletons
  holding dicts of jobs/sessions; nothing survives a server restart (output files in
  `outputs/` do). There is no database.
- **Threading model:** each job/live session gets a daemon thread; shared mutable state
  (latest JPEG frame, recording writer) is guarded by per-object locks. Route handlers
  read those fields directly for status polling.
- **Video codec handling:** OpenCV writers try `avc1` → `H264` → `mp4v` in order
  (duplicated in `jobs.py` and `live.py`). If the result isn't H.264 and `ffmpeg` is on
  PATH, jobs transcode the output for in-browser playback; otherwise the mp4v file is
  kept (downloadable but may not preview inline).
- `design/` holds static HTML dashboard mockups — reference material, not served by the app.
