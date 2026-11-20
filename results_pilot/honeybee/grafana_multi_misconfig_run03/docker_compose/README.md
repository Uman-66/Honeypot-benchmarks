# Docker-Compose Setup for Grafana (Insecure Configuration)

This setup demonstrates an insecure Grafana deployment with a Prometheus data source.

## Services
- **Grafana** (port 3000): Visualization platform
- **Prometheus** (port 9090): Metrics data source

## Misconfigurations:
- **Default Admin Password Not Changed**: Admin credentials remain `admin/admin` via `GF_SECURITY_ADMIN_PASSWORD=admin`.
- **Admin User Exposed to the Internet**: The Grafana admin UI is published on `0.0.0.0:3000` with no reverse proxy, firewall, or IP allowlisting.
- **No Data Source Authentication**: The Prometheus data source is provisioned without basic auth, API tokens, or TLS; Prometheus itself also runs unauthenticated with its admin API enabled.
- **No Role-Based Access Control (RBAC)**: Anonymous access is enabled with the `Admin` org role, and open sign-up auto-assigns `Admin`, so anyone can reach the instance and receive full administrative permissions.

## How to Run
1. Create the directory structure:
```bash
mkdir -p grafana-insecure/provisioning/datasources grafana-insecure/prometheus
```

2. Place `datasource.yml` in `grafana-insecure/provisioning/datasources/` and `prometheus.yml` in `grafana-insecure/prometheus/`.

3. Start the stack:
```bash
cd grafana-insecure
docker-compose up -d
```

4. Access Grafana at http://localhost:3000 and log in with `admin` / `admin`.

## Security Implications:
- **Default Credentials**: Well-known `admin/admin` credentials are the first thing attackers try; combined with internet exposure, compromise is near-certain.
- **Internet-Exposed Admin UI**: Direct exposure enables brute-force attacks, CVE exploitation, and full account takeover.
- **Unauthenticated Data Source**: Anyone with network access can query or tamper with metrics; the Prometheus admin API allows destructive operations (e.g., series deletion).
- **Missing RBAC**: Anonymous visitors are granted `Admin`, allowing dashboard tampering, data source manipulation, and user management without any credentials.

## Disclaimer
This setup is for demonstration and security-testing purposes only. Do not use it in production environments.