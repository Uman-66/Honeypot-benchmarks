# Docker Compose Setup for Grafana (Insecure Configuration)

This setup demonstrates an insecure Grafana deployment with Prometheus as its data source.

## Services
- **Grafana** (port 3000): Visualization platform with the admin interface.
- **Prometheus** (port 9090): Metrics backend used as Grafana's data source.

## Misconfigurations
1. **Default admin password not changed**: `GF_SECURITY_ADMIN_PASSWORD` is set to `admin`, leaving the well-known default `admin`/`admin` credentials in place.
2. **Admin user exposed to the internet**: Port 3000 is published on `0.0.0.0`, exposing the Grafana login page and admin account to the public internet.
3. **No data source authentication**: The Prometheus data source is provisioned without basic auth, API keys, or TLS. Prometheus itself is also exposed without authentication on port 9090.
4. **No RBAC**: Anonymous authentication is enabled with the `Admin` role, viewers can edit dashboards, and open sign-up is allowed. No users, teams, or permission tiers are configured.

## How to Run
1. Create the directory structure:
```bash
mkdir -p grafana-insecure/provisioning/datasources grafana-insecure/prometheus
```

2. Place the files as follows:
```
grafana-insecure/
├── docker-compose.yaml
├── provisioning/
│   └── datasources/
│       └── datasource.yml
└── prometheus/
    └── prometheus.yml
```

3. Start the stack:
```bash
cd grafana-insecure
docker-compose up -d
```

4. Access Grafana at `http://<host-ip>:3000` — you are granted Admin rights immediately without logging in (anonymous Admin access). If anonymous access is disabled, log in with `admin` / `admin`.

5. Verify the unauthenticated data source:
```bash
curl http://<host-ip>:9090/api/v1/query?query=up
```

## Security Implications
- **Default credentials**: The well-known `admin`/`admin` pair makes brute forcing unnecessary; an attacker gains full administrative control of the instance.
- **Internet exposure**: Publishing port 3000 on all interfaces exposes the admin interface to scanners and the public internet, enabling login attempts, exploitation of CVEs, and data exfiltration.
- **No data source authentication**: Anyone with network access can query or tamper with metrics; Prometheus on port 9090 can be scraped, abused for SSRF-style queries, or used to map the environment.
- **No RBAC**: Anonymous Admin access, editable data sources, and open sign-up mean any visitor can modify dashboards, alter data sources, delete data, or deface the instance — there is no separation between admin, editor, and viewer roles.

## Disclaimer
This setup is for demonstration and security-testing purposes only. Do not use it in production environments.