-- -----------------------------------------------------------------
-- init.sql - executed on first container startup
-- (mounted into /docker-entrypoint-initdb.d/)
-- -----------------------------------------------------------------

-- MISCONFIGURATION: Application account uses a trivially weak password
CREATE USER appuser WITH PASSWORD '123456';

-- MISCONFIGURATION: Application account is granted SUPERUSER rights
ALTER USER appuser WITH SUPERUSER;

GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;

CREATE TABLE public.notes (
    id SERIAL PRIMARY KEY,
    body TEXT
);

INSERT INTO public.notes (body) VALUES ('insecure demo data');