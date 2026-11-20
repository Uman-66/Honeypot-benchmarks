# Grafana Dockerfile with Insecure Configuration

This Dockerfile builds a Grafana container with intentional security misconfigurations. **Use with caution** as these settings expose Grafana to significant security risks.

## Misconfigurations Included

1. **Default admin password not changed** - `admin/admin` credentials are kept.
2. **Admin user exposed to the internet** - bound to `0.0.0.0` with brute-force protection disabled.
3. **No data source authentication** - the Prometheus data source is provisioned without any credentials.
4. **No RBAC** - anonymous users and self-registered users are granted the Admin role.

## Setup Instructions

1. Create the necessary directories:
```sh
mkdir -p grafana/insecure-configuration/provisioning/datasources
cd grafana/insecure-configuration
```

2. Place the `Dockerfile`, `grafana.ini`, and `provisioning/datasources/insecure-datasource.yaml` in the `grafana/insecure-configuration` directory.

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

## Access

Open `http://localhost:3000` - you are logged in as **Admin** automatically (anonymous access), or log in with `admin` / `admin`.

## Important Security Note
- **Default Credentials**: `admin/admin` is publicly known and never rotated.
- **Internet Exposure**: The admin UI listens on all interfaces with brute-force protection disabled.
- **Unauthenticated Data Source**: Metrics can be queried by anyone with UI access.
- **No RBAC**: Every visitor effectively has full administrator rights.

## Disclaimer
These configurations are intended for educational purposes to demonstrate potential security misconfigurations in Docker containers. **Do not use in production**.