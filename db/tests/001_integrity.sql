BEGIN;

DO $$
DECLARE
  tenant_a uuid;
  tenant_b uuid;
  brand_a uuid;
  brand_b uuid;
  outlet_a uuid;
  outlet_b uuid;
  logo_a uuid;
  category_a uuid;
  item_a uuid;
  variant_a uuid;
  offering_a uuid;
  table_a uuid;
  table_b uuid;
  visit_a uuid;
  access_a uuid;
  order_a uuid;
  line_a uuid;
  staff_a uuid;
BEGIN
  INSERT INTO tenant(slug, legal_name) VALUES ('integrity-alpha', 'Alpha') RETURNING id INTO tenant_a;
  INSERT INTO tenant(slug, legal_name) VALUES ('integrity-beta', 'Beta') RETURNING id INTO tenant_b;
  INSERT INTO media_asset(tenant_id, storage_key, mime_type, size_bytes, status)
    VALUES (tenant_a, 'alpha/logo.webp', 'image/webp', 100, 'READY') RETURNING id INTO logo_a;
  INSERT INTO brand(tenant_id, slug, display_name, logo_asset_id)
    VALUES (tenant_a, 'alpha', 'Alpha Kitchen', logo_a) RETURNING id INTO brand_a;
  INSERT INTO brand(tenant_id, slug, display_name)
    VALUES (tenant_b, 'beta', 'Beta Kitchen') RETURNING id INTO brand_b;
  BEGIN
    INSERT INTO brand(tenant_id, slug, display_name, logo_asset_id)
      VALUES (tenant_b, 'wrong-asset', 'Wrong', logo_a);
    RAISE EXCEPTION 'cross-tenant brand asset accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  INSERT INTO outlet(tenant_id, brand_id, slug, name)
    VALUES (tenant_a, brand_a, 'one', 'Alpha One') RETURNING id INTO outlet_a;
  INSERT INTO outlet(tenant_id, brand_id, slug, name)
    VALUES (tenant_b, brand_b, 'one', 'Beta One') RETURNING id INTO outlet_b;
  INSERT INTO outlet_brand_override(tenant_id, outlet_id, display_name)
    VALUES (tenant_a, outlet_a, 'Alpha at One');
  IF (SELECT coalesce(obo.display_name, b.display_name)
      FROM outlet o JOIN brand b ON b.id = o.brand_id
      LEFT JOIN outlet_brand_override obo ON obo.outlet_id = o.id
      WHERE o.id = outlet_a) <> 'Alpha at One' THEN
    RAISE EXCEPTION 'outlet brand override failed';
  END IF;
  IF (SELECT coalesce(obo.logo_asset_id, b.logo_asset_id)
      FROM outlet o JOIN brand b ON b.id = o.brand_id
      LEFT JOIN outlet_brand_override obo ON obo.outlet_id = o.id
      WHERE o.id = outlet_a) <> logo_a THEN
    RAISE EXCEPTION 'brand logo inheritance failed';
  END IF;
  IF (SELECT count(*) FROM outlet_event_mutex WHERE outlet_id IN (outlet_a, outlet_b)) <> 2 THEN
    RAISE EXCEPTION 'outlet event mutex rows missing';
  END IF;

  INSERT INTO menu_category(tenant_id, brand_id, name)
    VALUES (tenant_a, brand_a, 'Mains') RETURNING id INTO category_a;
  BEGIN
    INSERT INTO menu_item(tenant_id, brand_id, category_id, name)
      VALUES (tenant_b, brand_b, category_a, 'Wrong Tenant');
    RAISE EXCEPTION 'cross-tenant menu item accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  INSERT INTO menu_item(tenant_id, brand_id, category_id, name)
    VALUES (tenant_a, brand_a, category_a, 'Biryani') RETURNING id INTO item_a;
  INSERT INTO item_variant(tenant_id, brand_id, item_id, name)
    VALUES (tenant_a, brand_a, item_a, 'Regular') RETURNING id INTO variant_a;
  BEGIN
    INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id, price_paise)
      VALUES (tenant_b, brand_b, outlet_b, variant_a, 29900);
    RAISE EXCEPTION 'cross-brand offering accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id, price_paise, estimate_max_minutes)
    VALUES (tenant_a, brand_a, outlet_a, variant_a, 29900, 30) RETURNING id INTO offering_a;

  INSERT INTO dining_table(tenant_id, outlet_id, label, qr_token_hash)
    VALUES (tenant_a, outlet_a, 'T1', decode(repeat('aa', 32), 'hex')) RETURNING id INTO table_a;
  INSERT INTO dining_table(tenant_id, outlet_id, label, qr_token_hash)
    VALUES (tenant_b, outlet_b, 'T1', decode(repeat('ab', 32), 'hex')) RETURNING id INTO table_b;
  INSERT INTO dining_visit(tenant_id, outlet_id, table_id, visit_number)
    VALUES (tenant_a, outlet_a, table_a, 1) RETURNING id INTO visit_a;
  BEGIN
    INSERT INTO dining_visit(tenant_id, outlet_id, table_id, visit_number)
      VALUES (tenant_a, outlet_a, table_a, 2);
    RAISE EXCEPTION 'second active visit accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO dining_visit(tenant_id, outlet_id, table_id, visit_number)
      VALUES (tenant_a, outlet_a, table_b, 2);
    RAISE EXCEPTION 'wrong-outlet visit accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO browser_access(tenant_id, outlet_id, table_id, visit_id, expected_visit_number,
                               token_hash, expires_at)
      VALUES (tenant_a, outlet_a, table_a, visit_a, 2,
              decode(repeat('bb', 32), 'hex'), now() + interval '12 hours');
    RAISE EXCEPTION 'wrong access generation accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  INSERT INTO browser_access(tenant_id, outlet_id, table_id, visit_id, expected_visit_number,
                             token_hash, expires_at)
    VALUES (tenant_a, outlet_a, table_a, visit_a, 1,
            decode(repeat('cc', 32), 'hex'), now() + interval '12 hours') RETURNING id INTO access_a;
  INSERT INTO staff_user(email, password) VALUES ('integrity@example.invalid', '!unusable') RETURNING id INTO staff_a;
  INSERT INTO orders(tenant_id, outlet_id, visit_id, browser_access_id, source, display_ref,
                     idempotency_key, request_hash, subtotal_paise)
    VALUES (tenant_a, outlet_a, visit_a, access_a, 'CUSTOMER', 'A-1',
            'integrity-key-1', decode(repeat('dd', 32), 'hex'), 29900) RETURNING id INTO order_a;
  BEGIN
    INSERT INTO orders(tenant_id, outlet_id, visit_id, browser_access_id, source, display_ref,
                       idempotency_key, request_hash, subtotal_paise)
      VALUES (tenant_a, outlet_a, visit_a, access_a, 'CUSTOMER', 'A-2',
              'integrity-key-1', decode(repeat('ee', 32), 'hex'), 29900);
    RAISE EXCEPTION 'duplicate idempotency key accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO order_line(tenant_id, outlet_id, order_id, offering_id, item_name_snapshot,
                           variant_name_snapshot, dietary_type_snapshot, base_unit_paise,
                           quantity, queued_qty, ready_qty, estimate_min_minutes_snapshot,
                           estimate_max_minutes_snapshot)
      VALUES (tenant_a, outlet_a, order_a, offering_a, 'Biryani', 'Regular', 'UNSPECIFIED',
              29900, 2, 2, 1, 0, 30);
    RAISE EXCEPTION 'invalid quantity buckets accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  INSERT INTO order_line(tenant_id, outlet_id, order_id, offering_id, item_name_snapshot,
                         variant_name_snapshot, dietary_type_snapshot, base_unit_paise,
                         quantity, queued_qty, estimate_min_minutes_snapshot,
                         estimate_max_minutes_snapshot)
    VALUES (tenant_a, outlet_a, order_a, offering_a, 'Biryani', 'Regular', 'UNSPECIFIED',
            29900, 2, 2, 0, 30) RETURNING id INTO line_a;
  BEGIN
    INSERT INTO line_progress_event(tenant_id, outlet_id, line_id, from_state, to_state,
                                    quantity, line_revision, actor_id)
      VALUES (tenant_a, outlet_a, line_a, 'QUEUED', 'CANCELLED', 1, 2, staff_a);
    RAISE EXCEPTION 'cancellation without reason accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  INSERT INTO audit_event(tenant_id, outlet_id, action, entity_type, entity_id)
    VALUES (tenant_a, outlet_a, 'TEST', 'order', order_a);
  BEGIN
    DELETE FROM audit_event WHERE entity_id = order_a;
    RAISE EXCEPTION 'audit history deleted';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'audit history deleted' THEN RAISE; END IF;
  END;
END $$;

ROLLBACK;
