# Phase 1 database schema

The source of truth is the ordered SQL migration set in `db/migrations/`. PostgreSQL currently contains 29 tables, including `schema_migration`. All business primary keys are UUIDs except `domain_event` and `line_progress_event`, whose bigint IDs support ordered replay/history. Prices and totals are integer paise; times are `timestamptz`.

## Ownership and branding

`tenant` is the client account and security boundary. A tenant owns `brand` rows; each brand owns `outlet` rows. `media_asset` holds tenant-owned object-storage references, and `outlet_brand_override` selectively replaces a brand's names, images, colors, and contact fields for one outlet. `domain_mapping` maps a verified hostname to a brand or outlet. The application will resolve outlet values first, then brand defaults. Asset content must be validated at upload and served from object storage with safe content headers.

`staff_user` is designed for a future custom Django auth user; `staff_membership` grants tenant-wide owner/manager roles or outlet-specific roles. The API must authorize membership before setting tenant context.

## Menu and outlet controls

`menu_category`, `menu_item`, `item_variant`, `modifier_group`, and `modifier_option` belong to a brand. `outlet_offering` and `outlet_modifier` supply outlet-level price, availability, and version information. Composite foreign keys ensure an outlet cannot reference another tenant's or brand's catalogue. Referenced menu rows should be archived through `active = false` rather than deleted.

## Visits, orders, and billing

`dining_table` stores the permanent QR token hash and next visit number. `dining_visit` groups orders; a partial unique index permits only one `OPEN` or `CHECKOUT` visit per table. `browser_access` stores a hash of the browser capability and its expected visit generation. Composite foreign keys ensure a bound access belongs to that table and generation.

`orders` has a unique idempotency key per outlet and a request hash. Customer orders must reference access bound to the same visit. `order_line` stores immutable menu/price/estimate snapshots and current quantity buckets: queued, preparing, ready, served, cancelled. Their sum must equal the ordered quantity. `line_modifier` snapshots selected modifier names and prices. `line_progress_event` records state changes and requires a reason for cancellations. It is append-only.

`service_request` tracks waiter/bill requests and deduplicates open requests by browser access and kind. `closure_record` stores a unique external billing attestation for a visit. The existing POS remains authoritative for payment and invoices.

## Audit and event delivery

`audit_event` and `domain_event` are append-only. `outbox_entry` records delivery attempts. Every outlet receives an `outlet_event_mutex` row when created; transaction services will lock it before assigning event IDs. Outbox delivery can retry, so consumers must deduplicate event IDs.

## Invariants enforced later by transaction services

Database constraints establish ownership and shape, but several lifecycle rules require one transaction with row locks: a scan does not create a visit; the first order does; checkout freezes orders; billing closure advances `next_visit_number` once and revokes access. Order placement must recheck prices, availability, modifier ownership and selection bounds under locks. Progress changes must update quantity buckets and insert `line_progress_event` together. Staff role checks, menu version changes, and external bill reconciliation belong in the backend domain services.

When Django is added, its model/migration state must be aligned with these SQL-owned tables before using Django migrations for later changes. Do not let Django generate a second initial schema over them.
