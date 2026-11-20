# Docker-Compose Setup for Grafana (Insecure Configuration)

This setup demonstrates an insecure Grafana deployment backed by a Prometheus data source.

## Services
- **Grafana** (port 3000): Visualization platform with the admin UI exposed
- **Prometheus** (port 9090): Metrics backend, also exposed and unauthenticated

## Misconfigurations:
1. **Default Admin Password Not Changed**: Admin credentials are explicitly set to `admin` / `admin` via `GF_SECURITY_ADMIN_PASSWORD`.
2. **Admin User Exposed to the Internet**: Grafana is bound to `0.0.0.0:3000`, making the admin panel reachable from any host. Prometheus (9090) is likewise exposed.
3. **No Data Source Authentication**: The Prometheus data source is provisioned without basic auth, tokens, or TLS, and the Prometheus backend itself has no authentication layer.
4. **No RBAC**: Anonymous access is enabled with the `Admin` role (`GF_AUTH_ANONYMOUS_ORG_ROLE=Admin`), open self-signup is allowed (`GF_USERS_ALLOW_SIGN_UP=true`), and basic auth is disabled — every visitor effectively has full administrative control.

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
│       └── datasource.yaml
└── prometheus/
    └── prometheus.yml
```

3. Start the stack:
```bash
cd grafana-insecure
docker-compose up -d
```

4. Access Grafana at `http://<host-ip>:3000` and log in with `admin` / `admin` — or simply browse without logging in, since anonymous users receive the Admin role.

## Security Implications:
- **Default Credentials**: `admin/admin` is one of the most commonly exploited default credential pairs; automated scanners compromise exposed Grafana instances within minutes.
- **Internet Exposure**: A publicly reachable admin panel is subject to credential stuffing, known-CVE exploitation, and full data exfiltration.
- **Unauthenticated Data Source**: Any user can query, modify, or delete the data source; lack of TLS means credentials and metric data can be intercepted in transit. An editable data source also enables SSRF-style attacks by repointing it to internal hosts.
- **No RBAC / Anonymous Admin**: Granting the `Admin` role to anonymous users (`GF_AUTH_ANONYMOUS_ORG_ROLE=Admin`) gives every unauthenticated visitor rights to manage users, delete data sources, and tamper with dashboards and alerting.

## Remediation Recommendations:
- Change the admin password immediately and supply it via Docker secrets or a vault instead of plaintext environment variables.
- Bind Grafana to localhost or place it behind an authenticating reverse proxy, VPN, or SSO layer.
- Enable authentication on the data source (basic auth, API tokens, mTLS) and use HTTPS end-to-end.
- Disable anonymous access (`GF_AUTH_ANONYMOUS_ENABLED=false`), disable open signup, re-enable basic auth or configure OAuth/LDAP, and assign least-privilege roles (Viewer/Editor) with team- and folder-level permissions.

## Disclaimer
This setup is for demonstration and security-testing purposes only. Do not deploy it in production environments.