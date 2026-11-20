# PostgreSQL Dockerfile with Insecure Authentication Configuration

This Dockerfile builds a PostgreSQL container with intentional security misconfigurations. **Use with caution** as these settings expose the database to significant security risks.

## Setup Instructions

1. Create the necessary directories:
```sh
mkdir -p postgresql/insecure-authentication
cd postgresql/insecure-authentication
```

2. Place the `Dockerfile` in the `postgresql/insecure-authentication` directory.

## Build the Docker Image
To build the Docker image:
```sh
docker build -t insecure-postgres:15 ./postgresql/insecure-authentication
```

## Run the Docker Container
To run the PostgreSQL container:
```sh
docker run -d --name insecure-postgres -p 5432:5432 insecure-postgres:15
```

This command runs PostgreSQL in the background (`-d`), binds port `5432` on the container to port `5432` on the host, and uses the insecure PostgreSQL image.

## Important Security Notes
- **Weak Password**: The `postgres` superuser password is set to `postgres`, which is trivially easy to guess or brute-force.
- **Trust Authentication**: `POSTGRES_HOST_AUTH_METHOD=trust` allows all users to connect without any password, completely bypassing authentication.
- **Remote Access to All IPs**: `listen_addresses = '*'` binds PostgreSQL to every network interface, exposing it to the entire network.
- **Open pg_hba.conf Rules**: `host all all 0.0.0.0/0 trust` and `host all all ::/0 trust` permit passwordless logins from any IPv4 or IPv6 address.
- **EXPOSE 5432**: The default PostgreSQL port is exposed, allowing connections on this port.

## Disclaimer
These configurations are intended for educational purposes to demonstrate potential security misconfigurations in Docker containers. **Do not use in production.**