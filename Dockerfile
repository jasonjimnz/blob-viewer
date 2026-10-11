# syntax=docker/dockerfile:1
# --------------------------------------------------------------------------
# Blob Viewer — multi-stage build (small runtime image)
# Stage 1: build wheels into a clean venv
# Stage 2: slim runtime with only the venv copied over
# --------------------------------------------------------------------------

FROM python:3.13-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir .

# --------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="Blob Viewer" \
      org.opencontainers.image.description="Personal S3/MinIO bucket browser and file previewer" \
      org.opencontainers.image.authors="Jason Jiménez Cruz" \
      org.opencontainers.image.source="https://github.com/jasonjimnz/blob-viewer" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/jasonjimnz/blob-viewer"

# no desktop browser inside the container: server mode only
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BLOB_VIEWER_HOME=/data \
    PORT=8585

RUN groupadd -r blobviewer --gid=1000 \
 && useradd -r -g blobviewer --uid=1000 --home-dir=/data blobviewer \
 && mkdir -p /data \
 && chown -R blobviewer:blobviewer /data

COPY --from=builder --chown=blobviewer:blobviewer /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

USER blobviewer
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8585

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8585/api/health').status==200 else 1)"

ENTRYPOINT ["blob-viewer"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8585"]
