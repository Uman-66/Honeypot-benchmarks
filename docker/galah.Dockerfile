# docker/galah.Dockerfile
# Multi-stage build for galah.
# Build context must be the repo root (honeypot-benchmark/) so that both
# the galah/ source tree and this docker/ directory are reachable.
#
# Stage 1: compile
FROM golang:1.22-bookworm AS builder

WORKDIR /src

# Copy only the galah subtree so layer-cache is not invalidated by changes
# to other honeypots in the repo.
COPY galah/ .

RUN go mod download && \
    CGO_ENABLED=1 go build -o /galah-bin ./cmd/galah

# Stage 2: runtime
# debian:bookworm-slim carries bash and sh, needed for the entrypoint script.
# It also lets us add a non-root user and owns the logs directory correctly.
FROM debian:bookworm-slim

# ca-certificates: required for HTTPS calls to Fireworks API
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Runtime user — non-root, no login shell
RUN groupadd -g 1001 galah && \
    useradd -u 1001 -g galah -s /sbin/nologin -M galah

WORKDIR /galah

# Copy compiled binary
COPY --from=builder /galah-bin ./galah

# Copy the default config tree so galah can find config/config.yaml as a
# fallback, even though docker-compose mounts docker/galah-config.yaml
# over /galah/config/config.yaml at runtime.
COPY galah/config/ ./config/

# Entrypoint script: maps OPENAI_API_KEY → LLM_API_KEY and
# OPENAI_BASE_URL → LLM_SERVER_URL so that the project's shared .env
# works without duplicating secrets in compose environment: blocks.
# Copied from the docker/ directory (build context = repo root).
COPY docker/galah-entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Create the logs directory BEFORE the volume is mounted so Docker
# initialises the named volume with this directory already owned by uid 1001.
# If this is omitted the volume is initialised as root-owned and the
# non-root runtime user cannot write to it.
RUN mkdir -p /galah/logs && chown -R galah:galah /galah

USER galah

ENTRYPOINT ["./entrypoint.sh"]
