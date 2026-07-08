# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

# Dependency layer first so code edits don't invalidate the (large) install
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# Bake weights: app/pipeline.py auto-prefers the OpenVINO export when present
COPY yolov8n.pt ./
COPY yolov8n_openvino_model ./yolov8n_openvino_model
COPY app ./app
COPY static ./static

EXPOSE 8000
# Webcam capture is unavailable inside Docker Desktop; use uploads or RTSP.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
