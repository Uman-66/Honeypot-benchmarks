#!/bin/bash
# ============================================================
# init-insecure.sh
# Executed by the official entrypoint on first container startup.
# INTENTIONAL MISCONFIGURATIONS - DO NOT USE IN PRODUCTION
# ============================================================
set -e

# ------------------------------------------------------------
# MISCONFIGURATION 2 (re-enforced): Trust authentication
# Appends "trust" rules for ALL hosts to pg_hba.conf so password
# authentication is never required, even if the
# POSTGRES_HOST_AUTH_METHOD environment variable is later removed.
# Impact: Any client on any network can connect as any user
# (including the postgres superuser) with no password at all.
# ------------------------------------------------------------
echo "# MISCONFIGURATION: trust authentication for all hosts (no password required)" >> "$PGDATA/pg_hba.conf"
echo "host    all             all             0.0.0.0/0               trust" >> "$PGDATA/pg_hba.conf"
echo "host    all             all             ::/0                    trust" >> "$PGDATA/pg_hba.conf"

# ------------------------------------------------------------
# MISCONFIGURATION 1 (re-enforced): Weak password policy
# Creates an application account with a trivially weak password.
# Impact: Credentials are trivially guessable and, combined with
# password_encryption = 'md5', stored using weak MD5 hashing.
# ------------------------------------------------------------
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER appuser WITH PASSWORD '123456';
    GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO appuser;
EOSQL

echo "[init-insecure.sh] Insecure PostgreSQL configuration applied."