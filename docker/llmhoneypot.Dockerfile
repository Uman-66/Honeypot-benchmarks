# docker/llmhoneypot.Dockerfile
#
# Builds the PalisadeResearch/llm-honeypot honeypot against Cowrie 2.6.1
# (cowrie-base/, a local shallow clone already on disk).
#
# Build context: repo root (honeypot-benchmark/).
#
# Why NOT pip install cowrie:
#   PyPI cowrie is a different generation that uses command_modules instead of
#   __all__ for command registration. The overlay's init.py (which replaces
#   commands/__init__.py) uses the __all__ + import_module pattern that matches
#   cowrie-base (2.6.1) exactly. The PyPI version crashes with:
#     AttributeError: module 'cowrie.commands' has no attribute 'command_modules'
#
# Strategy: COPY cowrie-base/ into /home/cowrie/cowrie, create a venv, install
# dependencies from cowrie-base/requirements.txt (pinned), then install the
# project editably (pip install -e .), then overlay the modified command files
# exactly as the Makefile's install target does.

FROM python:3.10-slim

# ── System build dependencies ──────────────────────────────────────────────
# cryptography and bcrypt require libssl-dev + libffi-dev + build-essential.
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        libssl-dev \
        libffi-dev \
        build-essential \
        libpython3-dev && \
    rm -rf /var/lib/apt/lists/*

# ── Non-root runtime user ──────────────────────────────────────────────────
RUN groupadd -g 1001 cowrie && \
    useradd -u 1001 -g cowrie -s /usr/sbin/nologin -M -d /home/cowrie cowrie && \
    mkdir -p /home/cowrie && \
    chown cowrie:cowrie /home/cowrie

# ── Copy Cowrie source ─────────────────────────────────────────────────────
# cowrie-base/ is the pinned local source (v2.6.1); it is NOT excluded by
# the project root .dockerignore.
WORKDIR /home/cowrie/cowrie
COPY cowrie-base/ .

# ── Virtualenv + pinned dependencies ──────────────────────────────────────
# requirements.txt in cowrie-base/ pins all runtime deps exactly.
# pip install -e . registers the Twisted plugin entry point so that
# `twistd cowrie` resolves correctly.
RUN python -m venv cowrie-env && \
    cowrie-env/bin/pip install --no-cache-dir --upgrade pip setuptools && \
    cowrie-env/bin/pip install --no-cache-dir -r requirements.txt && \
    cowrie-env/bin/pip install --no-cache-dir -e .

# ── Overlay modified command files ─────────────────────────────────────────
# The Makefile install target copies these files into
#   src/cowrie/commands/
# and replaces the upstream versions.  We do the same here.
# IMPORTANT: init.py replaces __init__.py; it extends cowrie-base's __all__
# with the trap commands (df, ps, pwd_cmd, whoami, ls, cat8193, and the
# recovery commands) and uses the identical __all__+import_module mechanism.
COPY llm-honeypot/configs/cat8193.py        src/cowrie/commands/cat8193.py
COPY llm-honeypot/configs/df.py             src/cowrie/commands/df.py
COPY llm-honeypot/configs/disk_recover.py   src/cowrie/commands/disk_recover.py
COPY llm-honeypot/configs/fsck_repair.py    src/cowrie/commands/fsck_repair.py
COPY llm-honeypot/configs/id_service.py     src/cowrie/commands/id_service.py
COPY llm-honeypot/configs/init.py           src/cowrie/commands/__init__.py
COPY llm-honeypot/configs/llm_prompts.py    src/cowrie/commands/llm_prompts.py
COPY llm-honeypot/configs/ls.py             src/cowrie/commands/ls.py
COPY llm-honeypot/configs/ps.py             src/cowrie/commands/ps.py
COPY llm-honeypot/configs/pwd_cmd.py        src/cowrie/commands/pwd_cmd.py
COPY llm-honeypot/configs/server_init.py    src/cowrie/commands/server_init.py
COPY llm-honeypot/configs/sysctl_recovery.py src/cowrie/commands/sysctl_recovery.py
COPY llm-honeypot/configs/whoami.py         src/cowrie/commands/whoami.py

# ── Overlay honeyfs files ──────────────────────────────────────────────────
# The Makefile copies these into honeyfs/ (the contents_path default).
# In cowrie-base the honeyfs tree lives at the repo root (not inside src/),
# and cowrie.cfg sets contents_path = honeyfs (relative to WORKDIR).
COPY llm-honeypot/configs/motd    honeyfs/etc/motd
COPY llm-honeypot/configs/version honeyfs/proc/version
COPY llm-honeypot/configs/passwd  honeyfs/etc/passwd

# ── Runtime directories ────────────────────────────────────────────────────
# Create log, state, tty, downloads, and etc directories owned by cowrie
# BEFORE named volumes are mounted.  A root-owned empty volume causes
# PermissionError for uid 1001 on first write.
RUN mkdir -p \
        var/log/cowrie \
        var/lib/cowrie/tty \
        var/lib/cowrie/downloads \
        var/run \
        etc && \
    chown -R cowrie:cowrie /home/cowrie/cowrie

# ── Config ─────────────────────────────────────────────────────────────────
# docker/llmhoneypot.cowrie.cfg overrides the upstream etc/cowrie.cfg.dist.
# It is copied to etc/cowrie.cfg which is the default config path Cowrie reads.
COPY docker/llmhoneypot.cowrie.cfg etc/cowrie.cfg

# ── userdb.txt ─────────────────────────────────────────────────────────────
# Format per cowrie-base/etc/userdb.example:
#   field1:field2(unused):field3
#   field1 = username, field3 = password
#   '*' = wildcard, '!' prefix = deny
# Entries below accept root/toor and guest/guest exactly.
RUN printf 'root:x:toor\nguest:x:guest\n' > etc/userdb.txt && \
    chown cowrie:cowrie etc/userdb.txt etc/cowrie.cfg

USER cowrie

# ── Start command ──────────────────────────────────────────────────────────
# Matches the systemd ExecStart in llm-honeypot/configs/llm-honeypot.service:
#   twistd --umask 0022 --nodaemon --pidfile= -l - cowrie
# --nodaemon: foreground (no daemon)
# --pidfile=: empty string disables pidfile creation (same as the service unit)
# -l -: log to stdout
# cowrie: the Twisted plugin name (registered by pip install -e .)
# The venv bin/ is first on PATH so twistd from the venv is used.
ENV PATH="/home/cowrie/cowrie/cowrie-env/bin:${PATH}"
ENTRYPOINT ["twistd", "--umask", "0022", "--nodaemon", "--pidfile=", "-l", "-", "cowrie"]
