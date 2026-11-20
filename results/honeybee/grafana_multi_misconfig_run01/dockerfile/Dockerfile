# ============================================================================
# Grafana Dockerfile with INTENTIONAL security misconfigurations
# Purpose: Educational demonstration of common Grafana container misconfigurations
# WARNING: DO NOT use this image in production!
# ============================================================================

# Use the official Grafana image (pinned version)
FROM grafana/grafana:10.2.0

# ----------------------------------------------------------------------------
# MISCONFIGURATION 1: Default admin password not changed
# The well-known default credentials (admin/admin) are explicitly kept.
# Impact: Anyone can log in as administrator using publicly known defaults,
#         gaining full control over dashboards, users, and data sources.
# ----------------------------------------------------------------------------
ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_SECURITY_ADMIN_PASSWORD=admin

# ----------------------------------------------------------------------------
# MISCONFIGURATION 2: Admin user exposed to the internet
# Grafana is bound to all network interfaces (0.0.0.0) and brute-force
# login protection is disabled.
# Impact: The admin login page is reachable from any network; unlimited
#         password guessing / credential stuffing becomes trivial.
# ----------------------------------------------------------------------------
ENV GF_SERVER_HTTP_ADDR=0.0.0.0
ENV GF_AUTH_DISABLE_BRUTE_FORCE_LOGIN=true

# Copy the insecure Grafana configuration:
#  - Anonymous access enabled with the Admin role (no RBAC)
#  - Open self-signup that auto-assigns the Admin role
COPY grafana.ini /etc/grafana/grafana.ini

# ----------------------------------------------------------------------------
# MISCONFIGURATION 3: No data source authentication
# The provisioned Prometheus data source has no basic auth, no API token,
# and no TLS client certificate.
# Impact: Every user (including anonymous visitors) can read all metrics
#         exposed by the data source; sensitive telemetry leaks freely.
# ----------------------------------------------------------------------------
COPY provisioning/datasources/insecure-datasource.yaml /etc/grafana/provisioning/datasources/insecure-datasource.yaml

# ----------------------------------------------------------------------------
# MISCONFIGURATION 4: Failure to set up role-based access control (RBAC)
# grafana.ini grants the Admin role to anonymous users and to every
# self-registered account. There is no role separation at all.
# Impact: Any visitor can manage users, delete data sources, and modify
#         dashboards; there is no accountability or least privilege.
# ----------------------------------------------------------------------------

# Expose the Grafana web UI publicly on the default port
EXPOSE 3000

# The official entrypoint (/run.sh) starts Grafana and automatically loads
# /etc/grafana/grafana.ini — the insecure configuration copied above.
