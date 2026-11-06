# syntax=docker/dockerfile:1
# docker/honeybee.Dockerfile
#
# Streamlit UI that wraps an LLM to *generate* misconfigured Docker artifacts.
# honeybee is NOT a honeypot; see HONEYBEE_CHANGES.md for classification.
#
# Build context MUST be the project root:
#   docker build -f docker/honeybee.Dockerfile -t honeybee .
#
# Secrets NEVER baked in: OPENAI_API_KEY comes from runtime env_file only.
# Docker CLI is intentionally NOT installed — the deploy feature is disabled.
# No docker.sock mount — see compose file.

FROM python:3.11-slim

# Unbuffered output for readable logs.
ENV PYTHONUNBUFFERED=1

# ── System packages ───────────────────────────────────────────────────────────
# libmagic1: required by python-magic (scapy dependency chain).
# No gcc needed; all wheels have pre-built binaries on 3.11-slim.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libmagic1 && \
    rm -rf /var/lib/apt/lists/*

# ── Non-root runtime user (UID 10001) ─────────────────────────────────────────
RUN useradd -m -u 10001 -d /app honey

WORKDIR /app

# ── Install honeybee from the build-context copy of its source ────────────────
# We copy requirements first to benefit from layer caching, then the full
# package so a source-only change does not re-install all dependencies.
COPY honeybee/requirements.txt /tmp/hb_requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/hb_requirements.txt

# Copy the honeybee source package and install it.
# SETUPTOOLS_SCM_PRETEND_VERSION is required because the build context does not
# include the .git directory, so setuptools-scm cannot infer the version from
# git history and raises LookupError.  We hard-pin the version that matches
# honeybee/__init__.py (__version__ = "0.1.1").
COPY honeybee/ /app/honeybee_src/
RUN --mount=type=cache,target=/root/.cache/pip \
    SETUPTOOLS_SCM_PRETEND_VERSION=0.1.1 \
    pip install --no-cache-dir /app/honeybee_src/

# ── Environment variable for data directory ───────────────────────────────────
# query_history.py reads DATA_DIR to decide where to write .qhistory files.
# We point it at /app/data which is backed by a named volume.
ENV DATA_DIR=/app/data

# ── Pre-create writable directories owned by honey ───────────────────────────
# .qhistory is where query_history.py writes per-query JSON files.
# Streamlit writes its own config/cache under ~/.streamlit inside the container.
RUN mkdir -p /app/data/.qhistory && \
    chown -R honey:honey /app

# ── Streamlit headless configuration ─────────────────────────────────────────
# Written as the honey user's config so `honeybee` picks it up at startup.
# serverAddress / serverPort ensure we bind 0.0.0.0:8501 INSIDE the container
# (the compose file maps that to 127.0.0.1:2229 on the host).
# browser.gatherUsageStats=false disables all Streamlit telemetry.
RUN mkdir -p /app/.streamlit && \
    printf '[server]\nheadless = true\naddress = "0.0.0.0"\nport = 8501\nenableCORS = false\nenableXsrfProtection = true\n\n[browser]\ngatherUsageStats = false\n' \
    > /app/.streamlit/config.toml && \
    chown -R honey:honey /app/.streamlit

# ── Runtime ───────────────────────────────────────────────────────────────────
USER honey

# .qhistory must be the CWD for the relative HISTORY_PATH in query_history.py
# (it does `Path(__file__).parent.joinpath(".qhistory")` which resolves
# relative to the installed package inside site-packages, so the CWD does not
# matter — but the named volume is mounted at /app/data).
# We set HOME so Streamlit finds /app/.streamlit/config.toml.
ENV HOME=/app

EXPOSE 8501

# Run via the installed console script; pass Streamlit flags headlessly.
CMD ["honeybee", "--", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
