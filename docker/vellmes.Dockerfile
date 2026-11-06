# syntax=docker/dockerfile:1
# docker/vellmes.Dockerfile
#
# SSH honeypot wrapper around VelLMes-AI-Deception-Framework (shelLM / SSH mode).
#
# Build context MUST be the project root:
#   docker build -f docker/vellmes.Dockerfile -t vellmes .
#
# Secrets are NOT baked in: OPENAI_API_KEY and OPENAI_BASE_URL come from
# the env_file in the compose file at runtime.

FROM python:3.11-slim

# Ensure Python stdout/stderr is unbuffered everywhere (child processes too).
ENV PYTHONUNBUFFERED=1

# ── System packages ───────────────────────────────────────────────────────────
# gcc + libffi-dev: required to build cffi (cryptography/asyncssh dependency).
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# ── Non-root runtime user (UID 10001) ─────────────────────────────────────────
RUN useradd -m -u 10001 -d /app honey

WORKDIR /app

# ── SSH wrapper dependencies (asyncssh etc.) ─────────────────────────────────
COPY docker/vellmes.requirements.txt /tmp/wrapper_requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/wrapper_requirements.txt

# ── VelLMes application dependencies ─────────────────────────────────────────
# Installed AFTER wrapper deps so openai SDK is present for VelLMes.py.
COPY VelLMes-AI-Deception-Framework/requirements.txt /tmp/vellmes_requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/vellmes_requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
# Copy the whole VelLMes repo under /app/vellmes/
COPY VelLMes-AI-Deception-Framework/ /app/vellmes/

# Copy the SSH wrapper and the benchmark config
COPY docker/vellmes_ssh_wrapper.py /app/wrapper.py
COPY docker/vellmes_configSSH.yml  /app/vellmes/configSSH_bench.yml

# ── Pre-create the logs directory owned by honey ─────────────────────────────
# Named volume mounts happen AFTER container start; Docker copies directory
# ownership from the image layer to the volume on first use.
RUN mkdir -p /app/logs /app/hostkeys && \
    chown -R honey:honey /app

# ── Runtime ───────────────────────────────────────────────────────────────────
USER honey

EXPOSE 2228

CMD ["python", "/app/wrapper.py"]
