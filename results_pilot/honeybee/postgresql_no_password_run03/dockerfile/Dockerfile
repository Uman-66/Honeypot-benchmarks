# ============================================================
# PostgreSQL Dockerfile with INTENTIONAL security misconfigurations
# DO NOT USE IN PRODUCTION - for educational/testing purposes only
# ============================================================

# Use the official PostgreSQL image (version 13)
FROM postgres:13

# ------------------------------------------------------------
# MISCONFIGURATION 1: Weak password policy
# The superuser password is set to a trivially guessable value.
# Impact: Attackers can guess or brute-force credentials and gain
# full superuser access to the database.
# ------------------------------------------------------------
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres

# ------------------------------------------------------------
# MISCONFIGURATION 2: Trust authentication (login without password)
# POSTGRES_HOST_AUTH_METHOD=trust makes the official entrypoint write
# "trust" rules into pg_hba.conf, so ANY client may connect as ANY
# user WITHOUT supplying a password.
# Impact: Complete authentication bypass for all remote clients.
# ------------------------------------------------------------
ENV POSTGRES_HOST_AUTH_METHOD=trust

# ------------------------------------------------------------
# MISCONFIGURATION 3: Remote access allowed from ALL IPs
# Appending listen_addresses = '*' to the config sample so the
# generated postgresql.conf accepts connections on every interface.
# Combined with trust authentication, the database is exposed to
# the entire network.
# Impact: Anyone who can reach the container can connect to the DB.
# ------------------------------------------------------------
RUN echo "# MISCONFIGURATION: listen on all interfaces (remote access from any IP)" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "listen_addresses = '*'" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "# MISCONFIGURATION: store passwords with weak, deprecated MD5 hashing" >> /usr/share/postgresql/postgresql.conf.sample && \
    echo "password_encryption = 'md5'" >> /usr/share/postgresql/postgresql.conf.sample

# ------------------------------------------------------------
# Init script applied on first startup:
# - Re-enforces trust authentication rules in pg_hba.conf
# - Creates an additional account with a weak password
# ------------------------------------------------------------
COPY init-insecure.sh /docker-entrypoint-initdb.d/init-insecure.sh
RUN chmod +x /docker-entrypoint-initdb.d/init-insecure.sh

# Expose the PostgreSQL default port
EXPOSE 5432

# Start PostgreSQL with the misconfigured settings above
CMD ["postgres"]