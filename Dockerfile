# syntax=docker/dockerfile:1
#
# Voxa in a container: dub a video without installing Python, torch or ffmpeg on the host.
#
#   docker build -t voxa .
#   docker run --rm -v "$PWD:/data" voxa talk.mp4 --target_lang ru
#
# The defaults (google translation, edge speech) need no API key. To use a provider that
# does, pass it through:  -e OPENAI_API_KEY=...
FROM python:3.12-slim

# Links the published package back to this repository on GHCR.
LABEL org.opencontainers.image.source="https://github.com/akshinmrv/Voxa" \
      org.opencontainers.image.description="Dub any video into another language — and keep it in sync." \
      org.opencontainers.image.licenses="MIT"

# ffmpeg is the one non-Python dependency the pipeline cannot work without; voxa checks for
# it at startup and refuses to run if it is missing.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# The CPU-only torch wheel is a fraction of the CUDA one, and a container without a GPU
# cannot use CUDA anyway. Installing it first means pip treats the requirement as satisfied
# when the project is installed below.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

WORKDIR /src
# Only what the distribution itself needs — see .dockerignore for the rest.
COPY pyproject.toml README.md LICENSE ./
COPY voxa.py voxa_server.py ./
RUN pip install --no-cache-dir ".[serve]"

# Videos are mounted here. Voxa writes its work directory and the finished dub next to the
# input, so the result lands back on the host.
WORKDIR /data

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    # Model downloads are cached here; mount a volume on it to keep them between runs.
    XDG_CACHE_HOME=/cache

ENTRYPOINT ["voxa"]
CMD ["--help"]
