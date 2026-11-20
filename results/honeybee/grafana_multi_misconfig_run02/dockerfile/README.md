# Grafana Dockerfile with Insecure Configuration

This Dockerfile builds a Grafana container with intentional security misconfigurations. **Use with caution** as these settings expose Grafana to significant security risks.

## Misconfigurations Applied

- **Default admin password not changed**: `GF_SECURITY_ADMIN_PASSWORD` is left as `admin` (default credentials `admin/admin`).
- **Admin user exposed to the internet**: the server binds to `0.0.0.0` and port `3000` is exposed.
- **No data source authentication**: a Prometheus data source is provisioned without credentials, tokens, or TLS.
- **No RBAC**: anonymous authentication is enabled and every visitor receives the `Admin` org role; basic auth is disabled.

## Setup Instructions

1. Create the necessary directories:
```sh
mkdir -p grafana/insecure-configuration
cd grafana/insecure-configuration
```

2. Place the `Dockerfile` and `datasources.yml` in the `grafana/insecure-configuration` directory.

## Build the Docker Image
To build the Docker image:
```sh
docker build -t insecure-grafana:10.4.2 ./grafana/insecure-configuration
```

## Run the Docker Container
To run the Grafana container:
```sh
docker run -d --name insecure-grafana -p 3000:3000 insecure-grafana:10.4.2
```

This command runs Grafana in the background (`-d`), binds port `3000` on the container to port `3000` on the host, and uses the insecure Grafana image.

## Important Security Notes

- **Default credentials**: log in at `http://localhost:3000` with `admin/admin`.
- **Internet exposure**: the admin login page is reachable from any network interface.
- **Unauthenticated data source**: any user (including anonymous visitors) can query Prometheus through Grafana's proxy.
- **No RBAC**: every visitor is an implicit org Admin, so no permission checks are enforced.

## Disclaimer
These configurations are intended for educational purposes to demonstrate potential security misconfigurations in Docker containers. **Do not use in production.**