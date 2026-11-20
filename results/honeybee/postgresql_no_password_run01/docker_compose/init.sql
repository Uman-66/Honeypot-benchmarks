-- -----------------------------------------------------------------
-- INSECURE initialization script - FOR DEMONSTRATION ONLY
-- -----------------------------------------------------------------

-- MISCONFIGURATION: Application account uses a trivially weak password.
-- (Under trust auth the password is ignored, but if the method is ever
-- switched to md5/scram-sha-256 this password falls immediately.)
CREATE USER appuser WITH PASSWORD '123456';

-- MISCONFIGURATION: Superuser rights and broad grants for an app account.
ALTER USER appuser WITH SUPERUSER;
GRANT ALL PRIVILEGES ON DATABASE appdb TO appuser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO appuser;