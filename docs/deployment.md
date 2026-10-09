# Deployment plan

Assumption: “Resin” means **Render**. This document describes a development or demonstration deployment. A live restaurant ordering service needs persistent database backups, a responsive API during service hours, and reliable event delivery.

## What runs where

| Component | Local development | Free demonstration | Live restaurant use |
| --- | --- | --- | --- |
| PostgreSQL | Compose `db` service | External PostgreSQL provider such as Neon Free | Managed PostgreSQL with backups and tested restores |
| Django API | Compose `api` service | Render Free web service using this repository's Dockerfile | Always-on service, monitoring, deployment rollback |
| React portal | Future Vite dev server | Vercel Hobby for personal/noncommercial demonstration | A plan that permits commercial use, or another suitable static host |
| Menu/brand images | Local development storage | External object storage | Durable object storage and CDN |
| Event worker | Future local process/container | No durable free Render worker assumed | Dedicated worker or equivalent reliable process |

The local Compose database is **not** the production database. Render builds the Django application image from `Dockerfile`; its managed database or an external provider supplies `DATABASE_URL`. Vercel builds static React assets and receives only a public `VITE_API_BASE_URL`. Database credentials and Django secrets stay on Render, never in Vercel frontend variables.

## Deployment sequence

1. Create a PostgreSQL database in a managed provider. Set its region as close to Render as practical. Save its SSL-required connection URL as Render's `DATABASE_URL`.
2. Apply the SQL migrations from a trusted machine using `DATABASE_URL='...' .venv/bin/python db/migrate.py`. Render Free does not provide a pre-deploy command or shell; use a paid pre-deploy step later. Do not put `DATABASE_URL` in version control.
3. Deploy this repository's Dockerfile as a Render web service. Configure `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`, and `ASSET_BASE_URL`. The image binds to Render's `PORT` on `0.0.0.0`.
4. When built, deploy the React/Vite application to Vercel with `VITE_API_BASE_URL` pointing to the Render API. Prefer frontend and API subdomains of the same site for Lax cookies. If deploying to unrelated domains, browser third-party-cookie behavior needs explicit testing; `COOKIE_SAMESITE=None` requires HTTPS and may still be blocked by browser policy.
5. Store logos and menu photos in durable object storage. Do not rely on Render's local filesystem.
6. Before a real restaurant pilot, add backups, restore tests, monitoring, and a durable event worker. Exercise the full scan-to-order-to-billing flow during a Render cold start and database interruption.

## Free-tier limits affecting this product

- Render's Free web service spins down after 15 minutes without inbound traffic and can take about a minute to wake. Its local filesystem is ephemeral. This is unsuitable for a kitchen screen that must receive timely orders.
- Render Free PostgreSQL expires after 30 days and has no backups. Use it only for a disposable demonstration, not restaurant order history.
- Vercel Hobby is limited to personal, noncommercial use. A deployed client restaurant portal requires a plan or host whose terms permit commercial use.
- Vercel does not provide its former first-party Postgres product; its Postgres integrations use external providers. The Django API, not the Vercel frontend, should connect to the database.
- A free API instance and free database may both sleep or restart. The production design needs authoritative order snapshots and a durable outbox; SSE is only a delivery channel.

Useful provider references: [Render Free limitations](https://render.com/docs/free), [Render Docker deployment](https://render.com/docs/docker), [Vercel Hobby terms](https://vercel.com/docs/plans/hobby), [Vercel Postgres](https://vercel.com/docs/postgres), [PostgreSQL 18 container data path](https://hub.docker.com/_/postgres).
