# =====================================================================
# Grafana Dockerfile with INTENTIONAL security misconfigurations.
# FOR EDUCATIONAL/TESTING PURPOSES ONLY - DO NOT USE IN PRODUCTION.
# =====================================================================

# Use the official Grafana image
FROM grafana/grafana:10.4.2

# ---------------------------------------------------------------------
# MISCONFIGURATION 1: Default admin password not changed
# Grafana ships with the well-known default credentials admin/admin.
# Leaving them unchanged lets anyone log in with full admin rights.
# Impact: complete takeover of the Grafana instance, dashboard
# tampering, and pivoting into connected data sources.
# ---------------------------------------------------------------------
ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_SECURITY_ADMIN_PASSWORD=admin

# ---------------------------------------------------------------------
# MISCONFIGURATION 2: Admin user exposed to the internet
# Binding the HTTP server to 0.0.0.0 and exposing port 3000 makes the
# login page (and the default admin account) reachable from any
# network or interface.
# Impact: brute-force and credential-stuffing attacks against the
# admin account become trivial, especially combined with the default
# password above.
# ---------------------------------------------------------------------
ENV GF_SERVER_HTTP_ADDR=0.0.0.0
EXPOSE 3000

# ---------------------------------------------------------------------
# MISCONFIGURATION 3: No data source authentication
# A Prometheus data source is provisioned with no basic auth, no
# bearer token, and no TLS. Any viewer (or anonymous user, see below)
# can issue arbitrary queries against the backend metrics store.
# Impact: sensitive infrastructure metrics leak; the data source can
# be abused for reconnaissance or heavy queries that degrade backend
# performance.
# ---------------------------------------------------------------------
RUN mkdir -p /etc/grafana/provisioning/datasources
COPY datasources.yml /etc/grafana/provisioning/datasources/datasources.yml

# ---------------------------------------------------------------------
# MISCONFIGURATION 4: Failure to set up role-based access control
# Anonymous authentication is enabled and every anonymous visitor is
# automatically granted the built-in Admin org role. Basic auth is
# disabled so no per-user identity or permissions are enforced.
# Impact: anyone who can reach the port gets full admin capabilities:
# creating/deleting users, editing dashboards, and reading all data.
# ---------------------------------------------------------------------
ENV GF_AUTH_ANONYMOUS_ENABLED=true
ENV GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
ENV GF_AUTH_BASIC_ENABLED=false
ENV GF_USERS_ALLOW_SIGN_UP=true

# Start Grafana using the image's default entrypoint (/run.sh)
CMD ["run"]