FROM python:3.12-slim

# System packages needed to build keripy's native extensions (libsodium/blake3/etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    curl \
    git \
    libsodium-dev \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    KERI_BASER_MAP_SIZE=1099511627776

WORKDIR /app/castellan

# Install dependencies first so they're cached separately from source changes
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

COPY docker/scripts/ /app/castellan/docker/scripts/
RUN chmod +x /app/castellan/docker/scripts/*.sh

RUN mkdir -p /usr/local/var/keri/cf/main

ENTRYPOINT ["/bin/bash"]