FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY test_selector/ test_selector/

# Install into an isolated prefix so the runtime stage stays clean.
RUN pip install --no-cache-dir --prefix=/install .

# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# git is required when --from-git is used inside the container.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Mark the workspace volume so consumers can mount their repo here.
WORKDIR /repo

ENTRYPOINT ["test-selector"]
CMD []
