FROM python:3.11-slim

# Install uv and openssh-client (for ssh-keygen), create non-root user
RUN pip install uv && \
    apt-get update && apt-get install -y --no-install-recommends openssh-client && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -d /app honey

WORKDIR /app

# Copy project files (no .env, no .git — see .dockerignore)
COPY DECEIVE/ /app/

# Sync dependencies as root so the venv is installed under /app/.venv
# uv creates .venv relative to pyproject.toml, which is /app/.venv
RUN uv sync --frozen

# Generate SSH host key and set up log file, all owned by honey
RUN ssh-keygen -t rsa -b 4096 -N "" -f /app/SSH/ssh_host_key && \
    touch /app/SSH/ssh_log.log && \
    chown -R honey:honey /app

# Switch to non-root user for runtime
USER honey

# Tell uv where to put its cache (writable by honey)
ENV UV_CACHE_DIR=/app/.uv-cache

EXPOSE 8022

# Run from the repo root so that relative paths in config.ini resolve correctly
CMD ["uv", "run", "python", "SSH/ssh_server.py"]
