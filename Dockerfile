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
RUN uv sync --frozen --no-dev

COPY app ./app
COPY static ./static

# yolov8n.pt is not baked into the image (it's gitignored) — ultralytics
# downloads it automatically on first inference call, and app/pipeline.py
# will auto-prefer a '<stem>_openvino_model' export next to it if one is
# ever added. First request after a cold start will be a few seconds slower
# while the weights download.
RUN mkdir -p uploads ou