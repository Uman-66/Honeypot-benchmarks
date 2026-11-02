# syntax=docker/dockerfile:1
# docker/deceive.slim.Dockerfile
# Slim, fast image for DECEIVE SSH honeypot — openai provider only.
# No torch, CUDA, transformers, or other provider SDKs.
# Build from project root:
#   docker build -f docker/deceive.slim.Dockerfile -t deceive-slim .

FROM python:3.11-slim

# ── System packages ─────────────────────────────────────────────────────────
# openssh-client: provides ssh-keygen for generating the SSH host key at build time.
# We remove the apt lists afterwards to keep the layer small.
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Create the non-root runtime user with /app as its home directory.
RUN useradd -m -d /app honey

WORKDIR /app

# ── Python dependencies ──────────────────────────────────────────────────────
# Copy only the requirements file first so this expensive layer is cached
# independently of source-code changes.
COPY docker/deceive.requirements.txt /tmp/requirements.txt

# Use a BuildKit cache mount for pip's HTTP cache so repeated builds are fast.
# --no-deps is intentionally NOT set: we rely on pip's resolver to wire the
# already-pinned wheel graph correctly, but since everything is pinned pip
# should not upgrade anything.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
# Copy the DECEIVE project tree after the dependency layer so that code edits
# (SSH/, config.ini, prompt.txt) do not invalidate the pip install layer.
COPY DECEIVE/ /app/

# ── SSH host key + log file ───────────────────────────────────────────────────
# Generate the RSA host key with an empty passphrase.
# Pre-create the log file so it is writable without needing a directory.
# Transfer full ownership to the honey user.
# config.ini points to ssh_host_key (relative, resolved from SSH/), so the key
# must live at SSH/ssh_host_key relative to the WORKDIR (/app).
RUN ssh-keygen -t rsa -b 4096 -N "" -f /app/SSH/ssh_host_key && \
    touch /app/SSH/ssh_log.log && \
    chown -R honey:honey /app

# ── Runtime ──────────────────────────────────────────────────────────────────
USER honey

EXPOSE 8022

# Run directly with python (no uv needed — pip install above created the
# system-level packages, no venv required).
# WORKDIR is /app so that relative paths in config.ini (host_priv_key,
# log_file, prompt.txt) resolve correctly via SCRIPT_DIR.
CMD ["python", "SSH/ssh_server.py"]
