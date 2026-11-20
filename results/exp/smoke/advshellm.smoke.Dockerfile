# syntax=docker/dockerfile:1
# results/exp/smoke/advshellm.smoke.Dockerfile
#
# SMOKE-ONLY variant of docker/advshellm.Dockerfile. Same base image, same
# dependency list, same application code, same wrapper, same CMD. The only
# difference is the missing
#
#     RUN apt-get update && apt-get install -y gcc libffi-dev
#
# layer: on this machine deb.debian.org does not respond, and every dependency in
# advshellm.requirements.txt ships a manylinux wheel for CPython 3.11, so gcc is
# not needed to build cffi/cryptography here. This file exists only to run the
# Stage 2 five-command proxy smoke test; the benchmark's own Dockerfile is
# unchanged and remains the definition of the target.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN useradd -m -d /app honey

WORKDIR /app

COPY docker/advshellm.requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shelLM/AdvancedshelLM/codebase/ /app/codebase/
COPY docker/advshellm_ssh_wrapper.py /app/wrapper.py

RUN cp /app/codebase/LLM_Plugins/personalities/worker_backup.yml \
       /app/codebase/LLM_Plugins/personalities/worker.yml

RUN mkdir -p /app/codebase/logs && \
    chown -R honey:honey /app

USER honey

EXPOSE 2222

CMD ["/bin/sh", "-c", \
     "cp /app/codebase/LLM_Plugins/personalities/worker_backup.yml \
         /app/codebase/LLM_Plugins/personalities/worker.yml && \
      exec python /app/wrapper.py"]
