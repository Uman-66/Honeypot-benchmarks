# PostgreSQL Dockerfile with Insecure Configuration

This Dockerfile builds a PostgreSQL container with intentional security misconfigurations. **Use with caution** as these settings expose the database to significant security risks.

## Misconfigurations Applied

1. **Weak password policy** - The superuser password is `postgres`, an additional user `appuser` has the password `123456`, and passwords are stored using weak MD5 hashing.
2. **Trust authentication** - `pg_hba.conf` uses the `trust` method, allowing login as any user (including `postgres`) without any password.
3. **Remote access from all IPs** - `listen_addresses = '*'` makes PostgreSQL accept connections on every network interface.

## Setup Instructions

1. Create the necessary directories:
```sh
mkdir -p postgresql/insecure-configuration
cd postgresql/insecure-configuration
```

2. Place the `Dockerfile` and `init-insecure.sh` in the `postgresql/insecure-configuration` directory.

## Build the Docker Image
To build the Docker image:
```sh
docker build -t insecure-postgres:13 ./postgresql/insecure-configuration
```

## Run the Docker Container
To run the PostgreSQL container:
```sh
docker run -d --name insecure-postgres -p 5432:5432 insecure-postgres:13
```

This command runs PostgreSQL in the background (`-d`), binds port `5432` on the container to port `5432` on the host, and uses the insecure PostgreSQL image.

## Test the Insecure Configuration
From any machine that can reach the host, connect with no password:
```sh
psql -h <host-ip> -p 5432 -U postgres -d postgres
# When prompted for a password, press Enter (trust auth accepts anything)
```

## Important Security Notes
- **Weak Passwords**: `postgres/postgres` and `appuser/123456` are trivially guessable credentials.
- **Trust Authentication**: No password is required to connect as any user, including the superuser.
- **listen_addresses = '*'**: The database accepts connections from any IP address that can reach the container.
- **MD5 Password Storage**: Password hashes use the deprecated, weak MD5 algorithm.
- **EXPOSE 5432**: The default PostgreSQL port is exposed, allowing connections on this port.

## Disclaimer
These configurations are intended for educational purposes to demonstrate potential security misconfigurations in Docker containers. **Do not use in production.**