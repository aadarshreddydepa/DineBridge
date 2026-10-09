# DineBridge

The repository contains the PostgreSQL schema, Django REST API, and the mobile-first React customer menu. The staff portal is still to be built.

## Customer frontend

Run the API, then start Vite in another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [http://127.0.0.1:5173/demo?intro=1](http://127.0.0.1:5173/demo?intro=1) for a design preview, including the QR arrival animation. This preview uses sample food and disables checkout. A real table QR opens `/q/{token}`, creates a browser access cookie, and redirects to `/menu?outlet={id}`. The real page loads all restaurant identity and menu content from the API. Vite proxies `/api` and `/q` to the local API on port 8000. Use `127.0.0.1` consistently for both services.

The customer UI includes responsive menu browsing, search, dietary and category filters, item options, persistent basket, idempotent checkout, order polling, and service requests. Its arrival animation runs once per browser session per outlet and respects reduced-motion settings.

## Local database

Requires Docker Desktop or another Docker engine with Compose.

1. Copy the example environment file and replace `POSTGRES_PASSWORD` with a long random password:

   ```sh
   cp .env.example .env
   ```

2. Start PostgreSQL, apply migrations, and start the API:

   ```sh
   docker compose up -d db
   docker compose build api
   docker compose run --rm api python db/migrate.py
   docker compose up -d api
   docker compose ps
   ```

3. Open a SQL shell:

   ```sh
   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
   ```

4. Apply any pending schema migrations from the host or API container:

   ```sh
   .venv/bin/python db/migrate.py
   # or: docker compose run --rm api python db/migrate.py
   ```

The migration runner records applied versions in `schema_migration` and skips them on later runs. The current database has migrations `001_initial` and `002_cancellation_reason` applied. To rerun the rollback-only database integrity checks:

```sh
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/tests/001_integrity.sql
```

The schema and its key constraints are described in [docs/schema.md](docs/schema.md).

The API health check is [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz). API routes, cookies, roles, and the next work items are in [docs/api.md](docs/api.md). To run the rollback-only API flow test from the host:

```sh
uv sync
.venv/bin/python db/tests/smoke_api.py
```

The separate `db/tests/concurrency_api.py` check runs only against a disposable database whose name ends in `_concurrency_test`.

Create the first tenant and owner interactively after migrations:

```sh
docker compose exec api python manage.py bootstrap_tenant \
  --tenant-slug example-client --legal-name "Example Client" \
  --brand-slug example-brand --brand-name "Example Kitchen" \
  --outlet-slug main --outlet-name "Main Outlet" \
  --owner-email owner@example.com
```

This command prompts for an owner password. It does not seed a restaurant automatically.

The database listens only on `127.0.0.1` at `POSTGRES_PORT` (default `5432`). On the current development machine, `.env` uses **55432** because another local PostgreSQL server already uses 5432. A future Django backend running on the host can use `postgresql://dinebridge:<password>@127.0.0.1:55432/dinebridge` on this machine. A backend container on the same Compose network will use hostname `db` and port `5432` instead. URL-encode special characters in the password when constructing a connection URL.

The named Docker volume preserves data across `docker compose down` and container recreation. `docker compose down --volumes` deletes the local database. The PostgreSQL 18 image stores its data under `/var/lib/postgresql/18/docker`, so the volume is mounted at `/var/lib/postgresql`.

Configuration and deployment choices are in [docs/deployment.md](docs/deployment.md).
