FROM node:24.11.0-bookworm-slim@sha256:76d0ed0ed93bed4f4376211e9d8fddac4d8b3fbdb54cc45955696001a3c91152 AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend ./frontend
RUN npm run build --prefix frontend

FROM node:24.11.0-bookworm-slim@sha256:76d0ed0ed93bed4f4376211e9d8fddac4d8b3fbdb54cc45955696001a3c91152 AS promptfoo
WORKDIR /runtime
COPY backend/rilo/promptfoo_runtime/package.json backend/rilo/promptfoo_runtime/package-lock.json ./
RUN npm ci --omit=dev

FROM ghcr.io/astral-sh/uv:0.9.15-python3.13-bookworm-slim@sha256:03047771836471fab63b13546ccc20a8011ff0df64b4413052f1defdcd217a58 AS builder
WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv build --wheel

FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34 AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RILO_DATA_DIR=/data \
    RILO_HOSTED=1 \
    RILO_BIND_HOST=0.0.0.0 \
    RILO_PORT=8018
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 rilo \
    && useradd --uid 10001 --gid rilo --create-home --shell /usr/sbin/nologin rilo
WORKDIR /app
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=builder /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
COPY --from=promptfoo /runtime /opt/promptfoo-runtime
RUN RUNTIME_DIR="$(python -c 'import pathlib,rilo; print(pathlib.Path(rilo.__file__).parent / "promptfoo_runtime")')" \
    && mkdir -p "$RUNTIME_DIR" \
    && cp -a /opt/promptfoo-runtime/. "$RUNTIME_DIR/" \
    && rm -rf /opt/promptfoo-runtime
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY .env.example ./
RUN mkdir -p /data && chown -R rilo:rilo /data /app
USER rilo
VOLUME ["/data"]
EXPOSE 8018
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:8018/health || exit 1
CMD ["rilo", "serve", "--host", "0.0.0.0", "--port", "8018"]
