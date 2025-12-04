-- reset_lmanagement.sql
-- Drop the database and role (if they exist), recreate them,
-- set some sensible defaults, and grant privileges.

DROP DATABASE IF EXISTS lmanagement;
DROP ROLE IF EXISTS lmanagement;

CREATE USER lmanagement WITH PASSWORD 'lmanagement';
CREATE DATABASE lmanagement OWNER lmanagement;

-- Set defaults for the role
ALTER ROLE lmanagement SET client_encoding TO 'utf8';
ALTER ROLE lmanagement SET default_transaction_isolation TO 'read committed';
ALTER ROLE lmanagement SET timezone TO 'UTC';

-- Grant privileges on the database and public schema
GRANT ALL PRIVILEGES ON DATABASE lmanagement TO lmanagement;
\connect lmanagement
GRANT ALL ON SCHEMA public TO lmanagement;
