# syntax=docker/dockerfile:1
#
# Voxa in a container: dub a video without installing Python, torch or ffmpeg on the host.
#
#   docker build -t voxa .
#   docker run --rm -v "$PWD:/data" voxa talk.mp4 --target_lang ru
#
# The console, on http://127.0.0.1:8000 (published on loopback only, so it isn't on the LAN):
#
#   docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD:/data" voxa serve --host 0.0.0.0
#
# The defaults (google translation, edge speech) need no API key. To use a provider that
# does, pass it through:  -e OPENAI_API_KEY=...

# The console is a static build of web/, made here so the image needs no Node at run time.
# It is the same build the wheel on PyPI ships (see voxa_ui/).
FROM node:20-slim AS console
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Writes /src/voxa_ui/static.
RUN mkdir -p /src/voxa_ui && npm run build:console

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
# when the project is installed below. uv makes the environments `voxa engines install`
# puts optional engines in.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir uv

WORKDIR /src
# The dependencies first, from the metadata alone with empty stand-ins for the code, so a
# change to the code doesn't reinstall them. Only what the distribution itself needs is
# copied — see .dockerignore for the rest. openai-whisper pulls in triton on Linux for its
# CUDA kernels, which it imports only for a tensor on the GPU: a gigabyte this image never
# uses, so it goes.
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p voxa_ui voxa_engines \
    && touch voxa.py voxa_server.py voxa_ui/__init__.py voxa_engines/__init__.py \
    && pip install --no-cache-dir ".[serve]" \
    && pip uninstall -y voxa-dub triton \
    && rm -rf build ./*.egg-info voxa.py voxa_server.py voxa_ui voxa_engines
COPY voxa.py voxa_server.py ./
COPY voxa_ui/__init__.py voxa_ui/
COPY --from=console /src/voxa_ui/static voxa_ui/static/
COPY voxa_engines/ voxa_engines/
RUN pip install --no-cache-dir --no-deps . && rm -rf build ./*.egg-info

# Videos are mounted here. Voxa writes its work directory and the finished dub next to the
# input, so the result lands back on the host. `voxa serve` keeps its jobs here too.
WORKDIR /data

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    # Model downloads are cached here; mount a volume on it to keep them between runs.
    XDG_CACHE_HOME=/cache \
    UV_CACHE_DIR=/cache/uv \
    # Engines from `voxa engines install`, and the Python uv fetches for them; mount a
    # volume on it to keep them. The cache is often another volume, so uv copies rather
    # than links.
    VOXA_ENGINES_DIR=/engines \
    UV_PYTHON_INSTALL_DIR=/engines/.python \
    UV_LINK_MODE=copy

EXPOSE 8000
ENTRYPOINT ["voxa"]
CMD ["--help"]
