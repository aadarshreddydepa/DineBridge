# DineBridge

The repository contains the PostgreSQL schema, Django REST API, mobile-first React customer menu, and a staff portal for restaurant operations.

## Customer frontend

Run the API, then start Vite in another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [http://127.0.0.1:5173/demo?intro=1](http://127.0.0.1:5173/demo?intro=1) for a design preview, including the QR arrival animation. This preview uses sample food and disables checkout. A real table QR opens `/q/{token}`, creates a browser access cookie, and redirects to `/menu?outlet={id}`. The real page loads all restaurant identity and menu content from the API. Vite proxies `/api` and `/q` to the local API on port 8000. Use `127.0.0.1` consistently for both services.

The customer UI includes responsive menu browsing, search, dietary and category filters, item options, persistent basket, idempotent checkout, order polling, and service requests. Its arrival animation runs once per browser session per outlet and respects reduced-motion settings.

## Staff portal

Open [http://127.0.0.1:5173/staff](http://127.0.0.1:5173/staff) after starting Vite. Staff can sign in, select an assigned outlet, view active tables and kitchen work, acknowledge orders, progress dishes, resolve service requests, manage checkout and external POS billing, create and print table QRs, edit menu availability and prices, and control outlet branding and ordering. Tenant owners and managers can also add categories and dishes. The portal refreshes operational data every 10 seconds.

For a local demonstration on an **empty** database, run:

```sh
docker compose exec -T api python manage.py seed_local_demo > .local-demo-credentials.json
```

The command works only with `DJANGO_DEBUG=1` and returns a generated local owner password and three table QR URLs in the ignored credentials file. Set `ASSET_BASE_URL=https://images.unsplash.com` in local `.env` to display the seed's sample menu photos. The command refuses to run again after the demo tenant exists. For a real tenant, use `bootstrap_tenant` below and enter real menu content in the portal. Owner/manager staff can add categories, dishes, and up to 10 photos per dish (JPEG, PNG or WebP; 6 MB per file). The optional **Polish with AI** button requires `GROQ_API_KEY` in `.env` or `deploy/aws.env`; the key stays on the API server.

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

The migration runner records applied versions in `schema_migration` and skips them on later runs. The schema includes `001_initial`, `002_cancellation_reason`, and `003_menu_item_images`. To rerun the rollback-only database integrity checks:

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

Named Docker volumes preserve database data and uploaded menu photos across `docker compose down` and container recreation. `docker compose down --volumes` deletes both. The PostgreSQL 18 image stores its data under `/var/lib/postgresql/18/docker`, so the volume is mounted at `/var/lib/postgresql`.

Configuration and deployment choices are in [docs/deployment.md](docs/deployment.md).

For a hands-on single-server AWS trial, follow [docs/aws-trial.md](docs/aws-trial.md). It uses `compose.aws.yaml` to run the database, API and built frontend behind HTTPS on one EC2 instance. This is separate from the local Compose setup and does not require Vercel or Render.
