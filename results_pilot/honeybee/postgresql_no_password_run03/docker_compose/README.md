# Docker-Compose Setup for PostgreSQL (Insecure)

This setup demonstrates a deliberately insecure PostgreSQL configuration using Docker Compose.

## Misconfigurations:
- **Weak Password / No Password**: The superuser password is the trivial `admin123`, and `POSTGRES_HOST_AUTH_METHOD=trust` allows the database to run with password authentication effectively disabled.
- **Trust Authentication**: `pg_hba.conf` uses the `trust` method for local, IPv4 (`0.0.0.0/0`), and IPv6 (`::0/0`) clients, meaning anyone can connect as any role — including the `postgres` superuser — without a password.
- **Remote Access to All IPs**: `listen_addresses = '*'` in `postgresql.conf` combined with port `5432` published on `0.0.0.0` exposes the database to the entire network and potentially the internet.

## How to Run
1. Ensure the directory structure matches:
```
postgres-insecure-setup/
├── docker-compose.yaml
├── config/
│   ├── postgresql.conf
│   └── pg_hba.conf
└── README.md
```

2. Start the stack:
```bash
docker-compose up -d
```

3. Verify the insecure access (no password required, from any machine that can reach the host):
```bash
psql -h <host-ip> -p 5432 -U postgres -d appdb
# Connects WITHOUT any password prompt
```

## Security Implications:
- **Weak/No Password**: Attackers can trivially guess or bypass credentials, gaining immediate superuser access to the database.
- **Trust Authentication**: Eliminates the authentication layer entirely; any client that can reach the port owns the database. Data can be read, modified, or destroyed without any credentials.
- **Unrestricted Remote Access**: Publishing `5432` on all interfaces combined with `listen_addresses = '*'` maximizes the attack surface, enabling enumeration, brute force (if auth were enabled), and direct exploitation by anyone on the network.

## Remediation (for real deployments):
- Use strong, vault-managed passwords via Docker secrets or `.env` files excluded from version control.
- Use `scram-sha-256` authentication in `pg_hba.conf` with least-privilege role restrictions.
- Set `listen_addresses` to specific interfaces and avoid publishing the DB port; keep it on an internal Docker network only.

## Disclaimer
This setup is for demonstration and security-training purposes only. Do not use it in production environments.