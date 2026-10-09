# DineBridge

Phase 1 provides a local PostgreSQL environment for the restaurant ordering system. The backend, schema migrations, and portal are not in this repository yet.

## Local database

Requires Docker Desktop or another Docker engine with Compose.

1. Copy the example environment file and replace `POSTGRES_PASSWORD` with a long random password:

   ```sh
   cp .env.example .env
   ```

2. Start PostgreSQL:

   ```sh
   docker compose up -d db
   docker compose ps
   ```

3. Open a SQL shell:

   ```sh
   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
   ```

The database listens only on `127.0.0.1` at `POSTGRES_PORT` (default `5432`). On the current development machine, `.env` uses **55432** because another local PostgreSQL server already uses 5432. A future Django backend running on the host can use `postgresql://dinebridge:<password>@127.0.0.1:55432/dinebridge` on this machine. A backend container on the same Compose network will use hostname `db` and port `5432` instead. URL-encode special characters in the password when constructing a connection URL.

The named Docker volume preserves data across `docker compose down` and container recreation. `docker compose down --volumes` deletes the local database. The PostgreSQL 18 image stores its data under `/var/lib/postgresql/18/docker`, so the volume is mounted at `/var/lib/postgresql`.

Configuration and deployment choices are in [docs/deployment.md](docs/deployment.md).
