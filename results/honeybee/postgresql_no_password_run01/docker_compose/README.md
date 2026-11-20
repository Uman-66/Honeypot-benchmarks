# Docker-Compose Setup for PostgreSQL (Insecure)

This setup demonstrates an intentionally insecure PostgreSQL configuration.

## Misconfigurations
- **No Password / Weak Password Policy**: `POSTGRES_PASSWORD` is omitted and `POSTGRES_HOST_AUTH_METHOD=trust` is set. The `appuser` account uses the trivial password `123456` and holds `SUPERUSER` rights.
- **Trust Authentication**: `pg_hba.conf` uses the `trust` method for every address, so anyone can connect as any user (including `postgres`) without a password.
- **Remote Access to All IPs**: `postgresql.conf` sets `listen_addresses = '*'` and the container publishes port `5432` on all host interfaces.

## How to Run
1. Create the directory structure:
```bash
mkdir -p postgres-insecure/trust-auth/config
```

2. Place `postgresql.conf` and `pg_hba.conf` inside `config/`, and `init.sql` in the project root.

3. Start the stack:
```bash
docker-compose up -d
```

4. Connect WITHOUT a password from any machine that can reach the host:
```bash
psql -h <host-ip> -p 5432 -U postgres -d appdb
# No password prompt appears - trust authentication grants immediate access.
```

## Security Implications
- **Trust authentication**: Complete authentication bypass; any network peer can impersonate the database superuser.
- **listen_addresses = '*' + published port**: Exposes the database to the entire network, or the internet if the host is publicly reachable.
- **Weak/no passwords**: If authentication is ever switched to `md5`/`scram-sha-256`, the weak passwords fall instantly to brute force, and superuser rights maximize the blast radius.

## Disclaimer
This setup is for demonstration and security-testing purposes only. Never use it in production.