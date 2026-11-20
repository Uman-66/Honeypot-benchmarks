# Use the official Grafana image
FROM grafana/grafana:10.2.0

# ============================================================
# MISCONFIGURATION 1: Default admin password not changed
# ============================================================
# The admin username is left as the default "admin" and no
# GF_SECURITY_ADMIN_PASSWORD is set, so Grafana falls back to
# the well-known default password "admin".
# IMPACT: Anyone reaching the instance can log in with admin/admin
# and gain full control of dashboards, users, and data sources.
ENV GF_SECURITY_ADMIN_USER=admin
# NOTE: GF_SECURITY_ADMIN_PASSWORD is intentionally NOT set

# ============================================================
# MISCONFIGURATION 2: Admin user exposed to the internet
# ============================================================
# Grafana is bound to all network interfaces (0.0.0.0) and port
# 3000 is exposed, making the admin panel reachable from any host.
# IMPACT: Combined with the default credentials above, the admin
# panel is effectively public.
ENV GF_SERVER_HTTP_ADDR=0.0.0.0
EXPOSE 3000

# ============================================================
# MISCONFIGURATION 3: No data source authentication
# ============================================================
# A Prometheus data source is provisioned without any credentials
# (see provisioning/datasources/datasource.yaml).
# IMPACT: Unauthenticated access to backend metrics/data stores;
# any user or anonymous visitor can run arbitrary queries.
COPY provisioning/datasources/ /etc/grafana/provisioning/datasources/

# ============================================================
# MISCONFIGURATION 4: Failure to set up role-based access control (RBAC)
# ============================================================
# Anonymous authentication is enabled and every anonymous visitor
# is automatically granted the "Admin" organization role. There is
# no viewer/editor/admin separation and the login form is disabled.
# IMPACT: Every visitor receives full administrator permissions.
ENV GF_AUTH_ANONYMOUS_ENABLED=true
ENV GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
ENV GF_AUTH_DISABLE_LOGIN_FORM=true

# The default Grafana entrypoint starts the insecure instance