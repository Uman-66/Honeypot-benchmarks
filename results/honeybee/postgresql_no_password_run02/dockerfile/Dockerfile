# Use the official PostgreSQL image version 15
FROM postgres:15

# ============================================================
# MISCONFIGURATION 1: Weak password policy
# A trivially guessable password is set for the 'postgres'
# superuser. Attackers can easily brute-force or guess it.
# ============================================================
ENV POSTGRES_PASSWORD=postgres

# ============================================================
# MISCONFIGURATION 2: Trust authentication method
# POSTGRES_HOST_AUTH_METHOD=trust makes PostgreSQL accept ANY
# connection WITHOUT requiring a password at all. This renders
# the password above irrelevant and allows unauthenticated
# access to the entire database cluster.
# ============================================================
ENV POSTGRES_HOST_AUTH_METHOD=trust

# ============================================================
# MISCONFIGURATION 3: Remote access allowed from all IPs
# listen_addresses = '*' makes PostgreSQL listen on every
# network interface, exposing the database to the network.
# ============================================================
RUN echo "listen_addresses = '*'" >> /usr/share/postgresql/postgresql.conf.sample

# Permit passwordless 'trust' logins from ANY IPv4 and IPv6 address
RUN echo "host all all 0.0.0.0/0 trust" >> /usr/share/postgresql/pg_hba.conf.sample && \
    echo "host all all ::/0 trust" >> /usr/share/postgresql/pg_hba.conf.sample

# Expose the PostgreSQL default port to the outside world
EXPOSE 5432

# Start PostgreSQL using the official entrypoint, which applies
# the insecure configuration above on first initialization
CMD ["postgres"]