#!/bin/sh
# docker/galah-entrypoint.sh
#
# Maps the project's shared .env variable names to the names galah expects.
# This avoids duplicating secrets in compose environment: blocks and keeps
# secrets out of command lines and image layers.
#
# Mapping:
#   OPENAI_API_KEY  →  LLM_API_KEY     (galah --api-key / env:LLM_API_KEY)
#   OPENAI_BASE_URL →  LLM_SERVER_URL  (galah --server-url / env:LLM_SERVER_URL)
#
# Only sets the galah variables when they are not already set, so an operator
# can override them explicitly without touching .env.
#
# The key is never echoed, logged, or passed on the command line.
# Line endings must be LF (Unix). Do not convert to CRLF.

set -e

if [ -z "${LLM_API_KEY}" ] && [ -n "${OPENAI_API_KEY}" ]; then
    export LLM_API_KEY="${OPENAI_API_KEY}"
fi

if [ -z "${LLM_SERVER_URL}" ] && [ -n "${OPENAI_BASE_URL}" ]; then
    export LLM_SERVER_URL="${OPENAI_BASE_URL}"
fi

exec ./galah "$@"
