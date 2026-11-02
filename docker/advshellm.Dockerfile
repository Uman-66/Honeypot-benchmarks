# syntax=docker/dockerfile:1
# docker/advshellm.Dockerfile
#
# SSH honeypot wrapper around AdvancedshelLM (shelLM/AdvancedshelLM).
#
# Build context MUST be the project root:
#   docker build -f docker/advshellm.Dockerfile -t advshellm .
#
# Secrets are NOT baked in: OPENAI_API_KEY and OPENAI_BASE_URL come from
# the env_file in the compose file at runtime.

FROM python:3.11-slim

# Ensure Python stdout/stderr is unbuffered everywhere (child processes too).
# Without this, advancedShellm.py output is line-buffered when stdout is a pipe,
# meaning nothing arrives in the wrapper until a full line is written — even
# with python -u, this ENV is the belt-and-suspenders guarantee.
ENV PYTHONUNBUFFERED=1

# ── System packages ──────────────────────────────────────────────────────────
# gcc + libffi-dev: required to build cffi (cryptography/asyncssh dependency).
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# ── Non-root runtime user ────────────────────────────────────────────────────
RUN useradd -m -d /app honey

WORKDIR /app

# ── Python dependencies ──────────────────────────────────────────────────────
COPY docker/advshellm.requirements.txt /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
COPY shelLM/AdvancedshelLM/codebase/ /app/codebase/
COPY docker/advshellm_ssh_wrapper.py /app/wrapper.py

# ── Worker persona: reset from backup at build time ──────────────────────────
RUN cp /app/codebase/LLM_Plugins/personalities/worker_backup.yml \
       /app/codebase/LLM_Plugins/personalities/worker.yml

# ── Pre-create the logs directory and chown it BEFORE the named volume mounts ─
# CRITICAL: Docker mounts named volumes AFTER the container starts. If the
# mount target (/app/codebase/logs) does not exist in the image, Docker creates
# it as an empty directory owned by root. The child process (user honey,
# UID 1000) then fails with PermissionError on os.makedirs(logs_base_dir).
# Fix: create the directory in the image layer and chown it to honey so Docker
# uses the image's existing directory metadata as the volume mount point.
# Docker copies the image directory's ownership to a new (empty) named volume
# on first mount.
RUN mkdir -p /app/codebase/logs

# ── Ownership ────────────────────────────────────────────────────────────────
# chown after mkdir logs so that /app/codebase/logs is owned by honey.
# The named volume will inherit this ownership on first use.
RUN chown -R honey:honey /app

# ── Runtime ──────────────────────────────────────────────────────────────────
USER honey

EXPOSE 2222

# Entrypoint: reset worker.yml from backup on every container start/restart.
CMD ["/bin/sh", "-c", \
     "cp /app/codebase/LLM_Plugins/personalities/worker_backup.yml \
         /app/codebase/LLM_Plugins/personalities/worker.yml && \
      exec python /app/wrapper.py"]
