# API implementation status

Base URL: `http://127.0.0.1:8000`. All business routes use `/api/v1`, except QR bootstrap at `/q/{token}`. The API uses integer paise and UUID IDs. Responses return JSON and errors include a stable `code` and readable `message` for domain conflicts.

## Authentication and request flow

1. `GET /api/v1/csrf` sets a CSRF cookie and returns a token. Send it as `X-CSRFToken` on every POST or PATCH. Browser requests must include cookies.
2. A table QR opens `GET /q/{token}`. The API creates a 12-hour browser capability, sets an HttpOnly `db_access` cookie, and redirects to the configured frontend. Scanning does not create a visit.
3. Customer order submission needs `Idempotency-Key` and the access cookie. It creates the visit on the first committed order, rechecks item availability/version/price and modifier bounds, and returns the committed order.
4. Staff call `POST /api/v1/staff/login` and receive a 12-hour HttpOnly `db_staff` cookie. Staff authorization is checked against active tenant/outlet memberships on each request.

For production, use HTTPS, `DJANGO_DEBUG=0`, matching frontend/API site domains where possible, and explicit `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`, and `DATABASE_URL` values. The frontend receives only its public API base URL.

## Customer and public routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Database-backed health check. |
| GET | `/api/v1/csrf` | Issue CSRF token. |
| GET | `/api/v1/access` | Read the scanned table label and outlet for this browser capability. |
| GET | `/api/v1/outlets/{outlet_id}/config` | Effective brand/outlet identity, colors and asset URLs. |
| GET | `/api/v1/outlets/{outlet_id}/menu` | Available menu with portions, prices, modifiers and serving estimates. |
| GET | `/q/{token}` | Exchange permanent table QR for browser capability and redirect. |
| POST | `/api/v1/orders` | Place order; exact retry returns 200, new order returns 201. |
| GET | `/api/v1/orders` | List only this browser's submitted orders. |
| GET | `/api/v1/orders/{order_id}` | Read an order submitted from this browser access. |
| POST | `/api/v1/service-requests` | Request waiter or bill; repeat tap returns the open request. |

Order input example:

```json
{
  "lines": [{
    "offering_id": "UUID",
    "quantity": 2,
    "expected_version": 1,
    "expected_price_paise": 29900,
    "option_ids": [],
    "notes": "Mild"
  }]
}
```

## Staff routes

| Method | Route | Role/purpose |
| --- | --- | --- |
| POST | `/api/v1/staff/login` | Staff credentials. |
| POST | `/api/v1/staff/logout` | Clear staff cookie. |
| GET | `/api/v1/staff/me` | Active memberships. |
| GET | `/api/v1/staff/outlets/{outlet_id}/tables` | Active visits, unseen counts, requests and event cursor. |
| GET | `/api/v1/staff/outlets` | Active outlets and effective roles for the signed-in user. |
| GET | `/api/v1/staff/outlets/{outlet_id}/catalogue` | Categories, items, variants and all outlet offerings for menu editing. |
| GET | `/api/v1/staff/outlets/{outlet_id}/queue` | Persistent outstanding kitchen lines. |
| GET | `/api/v1/staff/visits/{visit_id}/orders` | Full visit orders and reconciliation summary. |
| GET | `/api/v1/staff/outlets/{outlet_id}/service-requests` | Open service requests. |
| POST | `/api/v1/staff/orders/{order_id}/seen` | Mark alert seen; never gates kitchen work. |
| PATCH | `/api/v1/staff/lines/{line_id}/progress` | Move quantity with `expected_revision`; manager handles cancellation. |
| POST | `/api/v1/staff/service-requests/{request_id}/resolve` | Resolve a request. |
| POST | `/api/v1/staff/visits/{visit_id}/checkout` | Freeze ordering and return reconciliation summary. |
| POST | `/api/v1/staff/visits/{visit_id}/cancel-checkout` | Restore OPEN state. |
| POST | `/api/v1/staff/visits/{visit_id}/complete-billing` | Attest to external POS bill and close exactly once. |
| GET | `/api/v1/staff/outlets/{outlet_id}/events?after=ID` | Seven-day JSON event replay. |
| GET | `/api/v1/staff/outlets/{outlet_id}/events/stream` | 30-second SSE stream with event IDs and heartbeats; reconnect with `Last-Event-ID`. |

Owner/manager configuration routes: `PATCH /staff/brands/{id}`, `PATCH /staff/outlets/{id}/branding`, `PATCH /staff/outlets/{id}/ordering`, `POST /staff/brands/{id}/categories`, `POST /staff/brands/{id}/items`, `POST /staff/items/{id}/variants`, `POST /staff/variants/{id}/modifier-groups`, `POST /staff/modifier-groups/{id}/options`, `POST /staff/outlets/{id}/offerings`, `PATCH /staff/outlets/{id}/offerings/{offering_id}`, `POST /staff/outlets/{id}/modifiers`, `POST /staff/outlets/{id}/tables`, and `POST /staff/tables/{id}/rotate-qr`. `POST /staff/outlets/{id}/quick-items` creates an item, Regular variant and outlet offering in one transaction for tenant owners/managers. These routes all have the `/api/v1` prefix. Table creation and QR rotation return a QR URL once; only its hash remains in PostgreSQL.

Menu photo routes for owners/managers: `GET`/`POST /api/v1/staff/items/{id}/images` lists/uploads photos (multipart field `images`; up to 10 photos per dish, 6 MB each), and `DELETE /api/v1/staff/items/{id}/images/{image_id}` removes one. `POST /api/v1/staff/outlets/{id}/description-draft` returns a reviewable AI suggestion when `OPENAI_API_KEY` is configured.

## Remaining work before a restaurant pilot

The staff portal now covers core restaurant operations. Before a real pilot, the API still needs customer order-event scoping, full catalogue edit/archive routes, a durable outbox delivery worker, request throttling, broader PostgreSQL concurrency/load tests, and deployment monitoring/backups. Menu photos are stored on a local Docker volume; use durable object storage and backups before real service. The portal currently polls every 10 seconds; the event stream is available but not integrated into the UI. The local smoke flow and a real two-phone first-order race test pass; they are not a live-service reliability gate. The existing POS remains authoritative for payment and invoices.
