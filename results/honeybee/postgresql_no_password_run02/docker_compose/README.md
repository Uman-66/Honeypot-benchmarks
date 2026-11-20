# Docker Compose Setup for PostgreSQL (Insecure)

This setup demonstrates an intentionally insecure PostgreSQL configuration.

## Misconfigurations

1. **Weak password / no password required**
   - `POSTGRES_PASSWORD: postgres` is a trivially weak, hardcoded superuser password.
   - `POSTGRES_HOST_AUTH_METHOD: trust` tells the official image to skip password setup entirely.

2. **Trust authentication (`pg_hba.conf`)**
   - All `local` and `host` lines use the `trust` method, so clients can connect as any user (including `postgres`) **without any password**.

3. **Remote access from all IPs (`postgresql.conf`)**
   - `listen_addresses = '*'` makes PostgreSQL listen on every interface.
   - The port mapping `"5432:5432"` publishes the database on all host interfaces, so anyone who can reach the host can reach the database.

## How to Run

1. Create the directory structure:

```bash
mkdir -p postgres-insecure/insecure-setup/config
```

2. Place `docker-compose.yaml`, `init.sql`, and this `README.md` in `postgres-insecure/insecure-setup`, and `postgresql.conf` / `pg_hba.conf` in the `config` subdirectory.

3. Start the stack:

```bash
cd postgres-insecure/insecure-setup
docker-compose up -d
```

4. Connect without a password from anywhere:

```bash
psql -h <docker-host-ip> -p 5432 -U postgres -d appdb
# No password prompt (or press Enter) - you are in as superuser.
```

## Security Implications

- **Weak/absent password**: Anyone who obtains the compose file (e.g., from a public repository) knows the superuser credentials.
- **Trust authentication**: Even rotated or stolen passwords provide no protection; authentication is effectively disabled.
- **listen_addresses = '*' + published port**: The database is exposed to the entire network (LAN, VPC, or the internet if the host is public), enabling data theft, tampering, and denial-of-service attacks.
- **Weak `appuser` password + SUPERUSER**: A compromised application account can drop databases, create roles, and read/write any data.

## Remediation (for real deployments)

- Use strong, rotated credentials stored in Docker secrets or a vault - never in the compose file.
- Use `scram-sha-256` in `pg_hba.conf` instead of `trust`.
- Bind `listen_addresses` to specific interfaces and do not publish port 5432 publicly; keep the database on an internal Docker network.
- Grant the application account only the privileges it needs.

## Disclaimer

This setup is for demonstration and security-training purposes only. Do not run it in production or on a publicly reachable host.