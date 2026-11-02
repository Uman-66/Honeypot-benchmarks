# docker/groundtruth_http.Dockerfile
# Real nginx 1.18.0 from ubuntu:20.04 — ground-truth HTTP target.
#
# Build from repo root:
#   docker build -f docker/groundtruth_http.Dockerfile -t gt-http .

FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -rf /var/lib/apt/lists/*

# The default /etc/nginx/sites-enabled/default is kept as-is; it serves the
# stock Ubuntu welcome page and returns 404 for unknown paths.
# server_tokens is NOT disabled so the Server header stays:
#   Server: nginx/1.18.0 (Ubuntu)

# Pre-create all directories that nginx 1.18.0 (Ubuntu package) writes to at
# startup.  /var/lib/nginx/body (and the other body/fastcgi/proxy/scgi/uwsgi
# subdirs) are created by nginx itself inside /var/lib/nginx — we only need the
# parent to exist with correct ownership.  The apt postinst creates these
# already, but we call mkdir -p defensively in case a layer caches oddly.
RUN mkdir -p \
      /var/lib/nginx \
      /var/cache/nginx \
      /var/log/nginx \
      /run

# Forward nginx access and error logs to Docker's log collector so that
# `docker logs` shows them.  The Ubuntu nginx package writes to files by
# default; replacing those files with symlinks to the standard streams makes
# logs visible without changing any nginx.conf directive or HTTP behaviour.
RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

EXPOSE 80

# Run nginx in the foreground.
# -g 'daemon off;' keeps the master process in the foreground so Docker
# can track it.  The pid file path comes from /etc/nginx/nginx.conf (default:
# /run/nginx.pid on Ubuntu 20.04, which is writable).
CMD ["nginx", "-g", "daemon off;"]
