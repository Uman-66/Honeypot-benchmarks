# docker/groundtruth_ssh.Dockerfile
# Real Ubuntu 20.04 sshd — ground-truth SSH target for the benchmark harness.
#
# Build from repo root:
#   docker build -f docker/groundtruth_ssh.Dockerfile -t gt-ssh .
#
# Credentials: guest / guest (password auth only, no root login)
# Listening port inside container: 22
# Mapped to host port 2225 in groundtruth_ssh.compose.yaml

FROM ubuntu:20.04

# Prevent apt from asking interactive questions
ENV DEBIAN_FRONTEND=noninteractive

# Install openssh-server only; keep the image small
RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-server && \
    rm -rf /var/lib/apt/lists/*

# Create guest user with a known password; no sudo group
# -m: create home directory; -s /bin/bash: set shell
RUN useradd -m -s /bin/bash guest && \
    echo 'guest:guest' | chpasswd

# Harden sshd_config:
#   PasswordAuthentication yes   – allow password login (only method)
#   PermitRootLogin no           – no root access
#   AllowUsers guest             – explicit allowlist
#   X11Forwarding no             – no X forwarding
#   AllowTcpForwarding no        – no port forwarding
#   AllowAgentForwarding no      – no agent forwarding
#   Subsystem                    – SFTP subsystem removed
#   UsePAM yes                   – required for password auth in Ubuntu
RUN printf '\
Port 22\n\
PasswordAuthentication yes\n\
PermitRootLogin no\n\
AllowUsers guest\n\
X11Forwarding no\n\
AllowTcpForwarding no\n\
AllowAgentForwarding no\n\
PermitTunnel no\n\
GatewayPorts no\n\
UsePAM yes\n\
PermitTTY yes\n\
LogLevel VERBOSE\n\
PrintMotd no\n\
AcceptEnv LANG LC_*\n\
' > /etc/ssh/sshd_config

# pam_loginuid cannot write /proc/self/loginuid in the container's default
# proc setup; keep the session accounting hook non-fatal.
RUN sed -i 's/^session[[:space:]]\+required[[:space:]]\+pam_loginuid\.so/session optional pam_loginuid.so/' /etc/pam.d/sshd

# Generate static host keys at build time so the fingerprint is stable across
# container restarts.  Keys are baked into the image layer.
RUN rm -f /etc/ssh/ssh_host_* && ssh-keygen -A
# sshd requires the privilege-separation directory to exist
RUN mkdir -p /run/sshd

EXPOSE 22

# Run sshd in foreground so Docker can track the process
CMD ["/usr/sbin/sshd", "-D", "-e"]
