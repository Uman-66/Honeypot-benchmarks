# Grafana Dockerfile with Insecure Configuration

This Dockerfile builds a Grafana container with intentional security misconfigurations. **Use with caution** as these settings expose Grafana to significant security risks.

## Misconfigurations Included

- **Default admin password not changed**: Grafana uses the well-known `admin` / `admin` credentials.
- **Admin user exposed to the internet**: Grafana binds to `0.0.0.0` and port `3000` is exposed.
- **No data source authentication**: The provisioned Prometheus data source has no credentials.
- **No RBAC**: Anonymous users are automatically granted the `Admin` role.

## Setup Instructions

1. Create the necessary directories:
```sh
mkdir -p grafana/insecure-configuration/provisioning/datasources
cd grafana/insecure-configuration
```

2. Place the `Dockerfile` in the `grafana/insecure-configuration` directory.

3. Place the `datasource.yaml` file in the `grafana/insecure-configuration/provisioning/datasources` directory.

## Build the Docker Image
To build the Docker image:
```sh
docker build -t insecure-grafana:10.2.0 ./grafana/insecure-configuration
```

## Run the Docker Container
To run the Grafana container:
```sh
docker run -d --name insecure-grafana -p 3000:3000 insecure-grafana:10.2.0
```

This command runs Grafana in the background (`-d`), binds port `3000` on the container to port `3000` on the host, and uses the insecure Grafana image.

## Important Security Notes

- **Default Credentials**: Log in with `admin` / `admin` — credentials are publicly known.
- **Exposed Admin Panel**: The admin interface is reachable from any network on port `3000`.
- **Unauthenticated Data Source**: The Prometheus data source requires no credentials; anyone can query it.
- **No RBAC**: Every anonymous visitor receives full `Admin` privileges; the login form is disabled.

## Disclaimer
These configurations are intended for educational purposes to demonstrate potential security misconfigurations in Docker containers. **Do not use in production**.