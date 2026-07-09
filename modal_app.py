"""
modal_app.py — Deploys the Bright Node Car Counter FastAPI app to Modal.

Deploy (the `modal` CLI isn't on PATH on this machine — always go through
`python -m modal`, and prefer `uv run` so it uses the project's venv):

    uv run python -m modal deploy modal_app.py
"""

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent

app = modal.App("car-counter")

# CPU-only: yolov8n doesn't need a GPU here, and the repo already ships an
# OpenVINO export (yolov8n_openvino_model/) that app/pipeline.py auto-prefers
# next to the .pt weights whenever it's present — 2-3x faster than plain
# PyTorch on CPU, same detections. Baking both in lets that existing
# preference logic pick the OpenVINO path automatically.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "ffmpeg",           # H.264 transcode fallback (see app/jobs.py)
        "libglib2.0-0", "libsm6", "libxext6", "libxrender1", "libgl1", "libgomp1",
    )
    .pip_install(
        "fastapi>=0.111",
        "python-multipart>=0.0.9",
        "ultralytics>=8.2",
        "supervision>=0.21",
        "opencv-python-headless>=4.9",
        "numpy>=1.26",
        "pydantic>=2.6",
        "openvino>=2024.0",
        "torch",
        "torchvision",
        extra_index_url="https://download.pytorch.org/whl/cpu",
    )
    .env({"CAR_COUNTER_WEIGHTS": "/root/yolov8n.pt"})
    .add_local_dir(str(ROOT / "app"), remote_path="/root/app", ignore=["__pycache__", "*.pyc"])
    .add_local_dir(str(ROOT / "static"), remote_path="/root/static")
    .add_local_file(str(ROOT / "yolov8n.pt"), remote_path="/root/yolov8n.pt")
    .add_local_dir(str(ROOT / "yolov8n_openvino_model"), remote_path="/root/yolov8n_openvino_model")
)


# max_containers=1: job/live-session state lives only in this process's
# memory (app/jobs.py JobManager, app/live.py LiveManager — no database,
# see CLAUDE.md), and uploaded/output files land on the container's local
# disk. Multiple containers would each have their own state, so a status
# poll or file download could 404 if Modal routed it to a different
# instance than the one that ran the job. Pinning to one container keeps
# the app's existing single-process assumptions intact; @modal.concurrent
# still lets that one container serve many simultaneous requests (uploads,
# polling, MJPEG previews) since FastAPI/asyncio + background threads don't
# need multiple processes for that.
@app.function(
    image=image,
    max_containers=1,
    scaledown_window=300,
    timeout=1800,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def fastapi_app():
    import sys
    sys.path.insert(0, "/root")

    from app.main import app as web_app

    return web_app
