BEGIN;

CREATE TABLE schema_migration (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenant (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  legal_name text NOT NULL CHECK (length(btrim(legal_name)) > 0),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE media_asset (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
  storage_key text NOT NULL CHECK (length(btrim(storage_key)) > 0),
  mime_type text NOT NULL CHECK (mime_type IN ('image/jpeg','image/png','image/webp','image/svg+xml')),
  width_px integer CHECK (width_px > 0),
  height_px integer CHECK (height_px > 0),
  size_bytes bigint NOT NULL CHECK (size_bytes > 0),
  alt_text text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','READY','REJECTED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, storage_key),
  UNIQUE (tenant_id, id),
  CHECK ((width_px IS NULL) = (height_px IS NULL))
);

CREATE TABLE brand (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
  slug text NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  display_name text NOT NULL CHECK (length(btrim(display_name)) > 0),
  short_name text,
  logo_asset_id uuid,
  icon_asset_id uuid,
  hero_asset_id uuid,
  primary_color text NOT NULL DEFAULT '#173F51' CHECK (primary_color ~ '^#[0-9A-Fa-f]{6}$'),
  accent_color text NOT NULL DEFAULT '#A5EADB' CHECK (accent_color ~ '^#[0-9A-Fa-f]{6}$'),
  support_email text,
  support_phone text,
  supported_locales jsonb NOT NULL DEFAULT '["en"]'::jsonb CHECK (jsonb_typeof(supported_locales) = 'array'),
  presentation jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(presentation) = 'object'),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug),
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, logo_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, icon_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, hero_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE outlet (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  slug text NOT NULL CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name text NOT NULL CHECK (length(btrim(name)) > 0),
  address text NOT NULL DEFAULT '',
  timezone text NOT NULL DEFAULT 'Asia/Kolkata',
  currency char(3) NOT NULL DEFAULT 'INR' CHECK (currency = 'INR'),
  ordering_enabled boolean NOT NULL DEFAULT false,
  delay_message text,
  menu_version bigint NOT NULL DEFAULT 1 CHECK (menu_version > 0),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (brand_id, slug),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, brand_id, id),
  FOREIGN KEY (tenant_id, brand_id) REFERENCES brand(tenant_id, id) ON DELETE RESTRICT
);

-- Null means inherit from brand. API combines these fields with brand defaults.
CREATE TABLE outlet_brand_override (
  outlet_id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  display_name text CHECK (display_name IS NULL OR length(btrim(display_name)) > 0),
  logo_asset_id uuid,
  icon_asset_id uuid,
  hero_asset_id uuid,
  primary_color text CHECK (primary_color ~ '^#[0-9A-Fa-f]{6}$'),
  accent_color text CHECK (accent_color ~ '^#[0-9A-Fa-f]{6}$'),
  support_email text,
  support_phone text,
  presentation jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(presentation) = 'object'),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, logo_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, icon_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, hero_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE domain_mapping (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
  hostname text NOT NULL UNIQUE CHECK (hostname = lower(hostname) AND hostname !~ '[/ :]'),
  brand_id uuid,
  outlet_id uuid,
  verified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(brand_id, outlet_id) = 1),
  FOREIGN KEY (tenant_id, brand_id) REFERENCES brand(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT
);

-- The future Django backend maps a custom user model to this table.
CREATE TABLE staff_user (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL CHECK (length(btrim(email)) > 3),
  password text NOT NULL,
  full_name text NOT NULL DEFAULT '',
  is_active boolean NOT NULL DEFAULT true,
  is_staff boolean NOT NULL DEFAULT false,
  is_superuser boolean NOT NULL DEFAULT false,
  last_login timestamptz,
  date_joined timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX staff_user_email_ci_uq ON staff_user(lower(email));

CREATE TABLE staff_membership (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES staff_user(id) ON DELETE RESTRICT,
  tenant_id uuid NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
  outlet_id uuid,
  role text NOT NULL CHECK (role IN ('OWNER','MANAGER','CASHIER','KITCHEN','WAITER')),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (outlet_id IS NOT NULL OR role IN ('OWNER','MANAGER')),
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX staff_membership_tenant_role_uq ON staff_membership(user_id, tenant_id, role) WHERE outlet_id IS NULL;
CREATE UNIQUE INDEX staff_membership_outlet_role_uq ON staff_membership(user_id, outlet_id, role) WHERE outlet_id IS NOT NULL;
CREATE INDEX staff_membership_outlet_active_idx ON staff_membership(outlet_id, role) WHERE active;

CREATE TABLE menu_category (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  name text NOT NULL CHECK (length(btrim(name)) > 0),
  translations jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(translations) = 'object'),
  display_order integer NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, brand_id, id),
  FOREIGN KEY (tenant_id, brand_id) REFERENCES brand(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX menu_category_brand_order_idx ON menu_category(brand_id, display_order) WHERE active;

CREATE TABLE menu_item (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  category_id uuid NOT NULL,
  name text NOT NULL CHECK (length(btrim(name)) > 0),
  description text NOT NULL DEFAULT '',
  translations jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(translations) = 'object'),
  dietary_type text NOT NULL DEFAULT 'UNSPECIFIED' CHECK (dietary_type IN ('UNSPECIFIED','VEGETARIAN','VEGAN','NON_VEGETARIAN')),
  allergens jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(allergens) = 'array'),
  image_asset_id uuid,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, brand_id, id),
  FOREIGN KEY (tenant_id, brand_id, category_id) REFERENCES menu_category(tenant_id, brand_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, image_asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX menu_item_category_active_idx ON menu_item(category_id) WHERE active;

CREATE TABLE item_variant (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  item_id uuid NOT NULL,
  name text NOT NULL CHECK (length(btrim(name)) > 0),
  display_order integer NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (item_id, name),
  UNIQUE (tenant_id, brand_id, id),
  FOREIGN KEY (tenant_id, brand_id, item_id) REFERENCES menu_item(tenant_id, brand_id, id) ON DELETE RESTRICT
);

CREATE TABLE modifier_group (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  variant_id uuid NOT NULL,
  name text NOT NULL CHECK (length(btrim(name)) > 0),
  min_choices integer NOT NULL DEFAULT 0 CHECK (min_choices >= 0),
  max_choices integer NOT NULL DEFAULT 1,
  display_order integer NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (max_choices >= min_choices),
  UNIQUE (tenant_id, brand_id, id),
  FOREIGN KEY (tenant_id, brand_id, variant_id) REFERENCES item_variant(tenant_id, brand_id, id) ON DELETE RESTRICT
);

CREATE TABLE modifier_option (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  group_id uuid NOT NULL,
  name text NOT NULL CHECK (length(btrim(name)) > 0),
  translations jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(translations) = 'object'),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, brand_id, id),
  FOREIGN KEY (tenant_id, brand_id, group_id) REFERENCES modifier_group(tenant_id, brand_id, id) ON DELETE RESTRICT
);

CREATE TABLE outlet_offering (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  variant_id uuid NOT NULL,
  price_paise bigint NOT NULL CHECK (price_paise >= 0),
  available boolean NOT NULL DEFAULT true,
  active boolean NOT NULL DEFAULT true,
  estimate_min_minutes integer NOT NULL DEFAULT 0 CHECK (estimate_min_minutes >= 0),
  estimate_max_minutes integer NOT NULL DEFAULT 0,
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (estimate_max_minutes >= estimate_min_minutes),
  UNIQUE (outlet_id, variant_id),
  UNIQUE (tenant_id, outlet_id, id),
  FOREIGN KEY (tenant_id, brand_id, outlet_id) REFERENCES outlet(tenant_id, brand_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, brand_id, variant_id) REFERENCES item_variant(tenant_id, brand_id, id) ON DELETE RESTRICT
);
CREATE INDEX outlet_offering_available_idx ON outlet_offering(outlet_id, variant_id) WHERE active AND available;

CREATE TABLE outlet_modifier (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  option_id uuid NOT NULL,
  price_delta_paise bigint NOT NULL DEFAULT 0 CHECK (price_delta_paise >= 0),
  available boolean NOT NULL DEFAULT true,
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (outlet_id, option_id),
  UNIQUE (tenant_id, outlet_id, id),
  FOREIGN KEY (tenant_id, brand_id, outlet_id) REFERENCES outlet(tenant_id, brand_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, brand_id, option_id) REFERENCES modifier_option(tenant_id, brand_id, id) ON DELETE RESTRICT
);

CREATE TABLE dining_table (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  label text NOT NULL CHECK (length(btrim(label)) > 0),
  active boolean NOT NULL DEFAULT true,
  next_visit_number bigint NOT NULL DEFAULT 1 CHECK (next_visit_number > 0),
  qr_token_hash bytea NOT NULL UNIQUE CHECK (octet_length(qr_token_hash) = 32),
  qr_rotated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (outlet_id, label),
  UNIQUE (tenant_id, outlet_id, id),
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE dining_visit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  table_id uuid NOT NULL,
  visit_number bigint NOT NULL CHECK (visit_number > 0),
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CHECKOUT','CLOSED')),
  started_at timestamptz NOT NULL DEFAULT now(),
  checkout_at timestamptz,
  closed_at timestamptz,
  revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
  UNIQUE (table_id, visit_number),
  UNIQUE (tenant_id, outlet_id, id),
  UNIQUE (tenant_id, outlet_id, table_id, id),
  UNIQUE (tenant_id, outlet_id, id, visit_number),
  CHECK ((status = 'OPEN' AND checkout_at IS NULL AND closed_at IS NULL) OR
         (status = 'CHECKOUT' AND checkout_at IS NOT NULL AND closed_at IS NULL) OR
         (status = 'CLOSED' AND checkout_at IS NOT NULL AND closed_at IS NOT NULL)),
  FOREIGN KEY (tenant_id, outlet_id, table_id) REFERENCES dining_table(tenant_id, outlet_id, id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX dining_visit_active_table_uq ON dining_visit(table_id) WHERE status IN ('OPEN','CHECKOUT');
CREATE INDEX dining_visit_outlet_status_idx ON dining_visit(outlet_id, status);

CREATE TABLE browser_access (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  table_id uuid NOT NULL,
  visit_id uuid,
  expected_visit_number bigint NOT NULL CHECK (expected_visit_number > 0),
  token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  last_used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, outlet_id, id),
  UNIQUE (tenant_id, outlet_id, visit_id, id),
  CHECK (expires_at > created_at),
  FOREIGN KEY (tenant_id, outlet_id, table_id) REFERENCES dining_table(tenant_id, outlet_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, table_id, visit_id) REFERENCES dining_visit(tenant_id, outlet_id, table_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, visit_id, expected_visit_number) REFERENCES dining_visit(tenant_id, outlet_id, id, visit_number) ON DELETE RESTRICT
);
CREATE INDEX browser_access_generation_idx ON browser_access(table_id, expected_visit_number);
CREATE INDEX browser_access_expiry_idx ON browser_access(expires_at);

CREATE TABLE orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  visit_id uuid NOT NULL,
  browser_access_id uuid,
  created_by_staff_id uuid REFERENCES staff_user(id) ON DELETE RESTRICT,
  source text NOT NULL CHECK (source IN ('CUSTOMER','STAFF')),
  display_ref text NOT NULL CHECK (length(btrim(display_ref)) > 0),
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 200),
  request_hash bytea NOT NULL CHECK (octet_length(request_hash) = 32),
  subtotal_paise bigint NOT NULL CHECK (subtotal_paise >= 0),
  placed_at timestamptz NOT NULL DEFAULT now(),
  seen_at timestamptz,
  seen_by_id uuid REFERENCES staff_user(id) ON DELETE RESTRICT,
  UNIQUE (outlet_id, idempotency_key),
  UNIQUE (tenant_id, outlet_id, id),
  CHECK ((source = 'CUSTOMER' AND browser_access_id IS NOT NULL AND created_by_staff_id IS NULL) OR
         (source = 'STAFF' AND browser_access_id IS NULL AND created_by_staff_id IS NOT NULL)),
  CHECK ((seen_at IS NULL) = (seen_by_id IS NULL)),
  FOREIGN KEY (tenant_id, outlet_id, visit_id) REFERENCES dining_visit(tenant_id, outlet_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, visit_id, browser_access_id) REFERENCES browser_access(tenant_id, outlet_id, visit_id, id) ON DELETE RESTRICT
);
CREATE INDEX orders_visit_placed_idx ON orders(visit_id, placed_at);
CREATE INDEX orders_outlet_placed_idx ON orders(outlet_id, placed_at);
CREATE INDEX orders_unseen_idx ON orders(outlet_id, placed_at) WHERE seen_at IS NULL;

-- Current quantities are mutually exclusive buckets. Their sum is always quantity.
CREATE TABLE order_line (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  order_id uuid NOT NULL,
  offering_id uuid NOT NULL,
  item_name_snapshot text NOT NULL,
  variant_name_snapshot text NOT NULL,
  dietary_type_snapshot text NOT NULL,
  allergens_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(allergens_snapshot) = 'array'),
  base_unit_paise bigint NOT NULL CHECK (base_unit_paise >= 0),
  modifier_unit_paise bigint NOT NULL DEFAULT 0 CHECK (modifier_unit_paise >= 0),
  quantity integer NOT NULL CHECK (quantity BETWEEN 1 AND 20),
  queued_qty integer NOT NULL,
  preparing_qty integer NOT NULL DEFAULT 0,
  ready_qty integer NOT NULL DEFAULT 0,
  served_qty integer NOT NULL DEFAULT 0,
  cancelled_qty integer NOT NULL DEFAULT 0,
  notes text NOT NULL DEFAULT '' CHECK (length(notes) <= 300),
  estimate_min_minutes_snapshot integer NOT NULL CHECK (estimate_min_minutes_snapshot >= 0),
  estimate_max_minutes_snapshot integer NOT NULL,
  ready_at timestamptz,
  served_at timestamptz,
  revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (queued_qty >= 0 AND preparing_qty >= 0 AND ready_qty >= 0 AND served_qty >= 0 AND cancelled_qty >= 0),
  CHECK (queued_qty + preparing_qty + ready_qty + served_qty + cancelled_qty = quantity),
  CHECK (estimate_max_minutes_snapshot >= estimate_min_minutes_snapshot),
  UNIQUE (tenant_id, outlet_id, id),
  FOREIGN KEY (tenant_id, outlet_id, order_id) REFERENCES orders(tenant_id, outlet_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, offering_id) REFERENCES outlet_offering(tenant_id, outlet_id, id) ON DELETE RESTRICT
);
CREATE INDEX order_line_order_idx ON order_line(order_id);

CREATE TABLE line_modifier (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  line_id uuid NOT NULL,
  outlet_modifier_id uuid NOT NULL,
  group_name_snapshot text NOT NULL,
  option_name_snapshot text NOT NULL,
  delta_paise_snapshot bigint NOT NULL CHECK (delta_paise_snapshot >= 0),
  UNIQUE (line_id, outlet_modifier_id),
  FOREIGN KEY (tenant_id, outlet_id, line_id) REFERENCES order_line(tenant_id, outlet_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, outlet_modifier_id) REFERENCES outlet_modifier(tenant_id, outlet_id, id) ON DELETE RESTRICT
);

CREATE TABLE line_progress_event (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  line_id uuid NOT NULL,
  from_state text NOT NULL CHECK (from_state IN ('QUEUED','PREPARING','READY')),
  to_state text NOT NULL CHECK (to_state IN ('PREPARING','READY','SERVED','CANCELLED')),
  quantity integer NOT NULL CHECK (quantity > 0),
  line_revision bigint NOT NULL CHECK (line_revision > 1),
  actor_id uuid NOT NULL REFERENCES staff_user(id) ON DELETE RESTRICT,
  reason text,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((from_state = 'QUEUED' AND to_state IN ('PREPARING','CANCELLED')) OR
         (from_state = 'PREPARING' AND to_state IN ('READY','CANCELLED')) OR
         (from_state = 'READY' AND to_state IN ('SERVED','CANCELLED'))),
  CHECK (to_state <> 'CANCELLED' OR length(btrim(reason)) > 0),
  FOREIGN KEY (tenant_id, outlet_id, line_id) REFERENCES order_line(tenant_id, outlet_id, id) ON DELETE RESTRICT
);
CREATE INDEX line_progress_event_line_idx ON line_progress_event(line_id, id);

CREATE TABLE service_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  visit_id uuid NOT NULL,
  browser_access_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('WAITER','BILL')),
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RESOLVED')),
  requested_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  resolved_by_id uuid REFERENCES staff_user(id) ON DELETE RESTRICT,
  CHECK ((status = 'OPEN' AND resolved_at IS NULL AND resolved_by_id IS NULL) OR
         (status = 'RESOLVED' AND resolved_at IS NOT NULL AND resolved_by_id IS NOT NULL)),
  FOREIGN KEY (tenant_id, outlet_id, visit_id) REFERENCES dining_visit(tenant_id, outlet_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, visit_id, browser_access_id) REFERENCES browser_access(tenant_id, outlet_id, visit_id, id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX service_request_open_access_uq ON service_request(browser_access_id, kind) WHERE status = 'OPEN';
CREATE INDEX service_request_open_outlet_idx ON service_request(outlet_id, requested_at) WHERE status = 'OPEN';

CREATE TABLE closure_record (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  visit_id uuid NOT NULL UNIQUE,
  external_bill_ref text NOT NULL CHECK (length(btrim(external_bill_ref)) > 0),
  external_total_paise bigint NOT NULL CHECK (external_total_paise >= 0),
  payment_method_label text NOT NULL CHECK (length(btrim(payment_method_label)) > 0),
  payment_confirmed_by_id uuid NOT NULL REFERENCES staff_user(id) ON DELETE RESTRICT,
  payment_confirmed_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, outlet_id, visit_id) REFERENCES dining_visit(tenant_id, outlet_id, id) ON DELETE RESTRICT
);

CREATE TABLE audit_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  actor_id uuid REFERENCES staff_user(id) ON DELETE RESTRICT,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  before_state jsonb,
  after_state jsonb,
  reason text,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX audit_event_outlet_time_idx ON audit_event(outlet_id, occurred_at DESC);

-- The application locks this row just before event insertion and transaction commit.
CREATE TABLE outlet_event_mutex (
  tenant_id uuid NOT NULL,
  outlet_id uuid PRIMARY KEY,
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT
);
CREATE FUNCTION create_outlet_event_mutex() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO outlet_event_mutex(tenant_id, outlet_id) VALUES (NEW.tenant_id, NEW.id);
  RETURN NEW;
END $$;
CREATE TRIGGER outlet_event_mutex_insert AFTER INSERT ON outlet
FOR EACH ROW EXECUTE FUNCTION create_outlet_event_mutex();

CREATE TABLE domain_event (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL,
  outlet_id uuid NOT NULL,
  visit_id uuid,
  event_type text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, outlet_id) REFERENCES outlet(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, outlet_id, visit_id) REFERENCES dining_visit(tenant_id, outlet_id, id) ON DELETE RESTRICT
);
CREATE INDEX domain_event_outlet_id_idx ON domain_event(outlet_id, id);

CREATE TABLE outbox_entry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id bigint NOT NULL UNIQUE REFERENCES domain_event(id) ON DELETE RESTRICT,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  last_error text
);
CREATE INDEX outbox_entry_pending_idx ON outbox_entry(next_attempt_at) WHERE processed_at IS NULL;

-- Historical ledgers are append-only; outbox delivery state is intentionally mutable.
CREATE FUNCTION reject_ledger_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$;
CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON audit_event
FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
CREATE TRIGGER domain_event_append_only BEFORE UPDATE OR DELETE ON domain_event
FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
CREATE TRIGGER line_progress_event_append_only BEFORE UPDATE OR DELETE ON line_progress_event
FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();

INSERT INTO schema_migration(version) VALUES ('001_initial');
COMMIT;
