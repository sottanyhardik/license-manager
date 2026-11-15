#!/bin/sh
# Runs ONCE, on first initialisation of an empty lm_pgdata volume (postgres
# image entrypoint). Creates the Master-Data Service role + database used by
# master-data-service/ (CI uses the same names). CREATEDB lets pytest create
# its test_master_data database. The main lmanagement role is POSTGRES_USER.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v mds_user="$MDS_DB_USER" -v mds_pass="$MDS_DB_PASSWORD" -v mds_db="$MDS_DB_NAME" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN CREATEDB PASSWORD %L', :'mds_user', :'mds_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'mds_user') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'mds_db', :'mds_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'mds_db') \gexec
SQL
