BEGIN;

CREATE TABLE menu_item_image (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  brand_id uuid NOT NULL,
  item_id uuid NOT NULL,
  asset_id uuid NOT NULL,
  display_order integer NOT NULL DEFAULT 0 CHECK (display_order >= 0),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (item_id, asset_id),
  FOREIGN KEY (tenant_id, brand_id, item_id) REFERENCES menu_item(tenant_id, brand_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, asset_id) REFERENCES media_asset(tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX menu_item_image_active_order_idx ON menu_item_image(item_id, display_order, id) WHERE active;

INSERT INTO schema_migration(version) VALUES ('003_menu_item_images');
COMMIT;
