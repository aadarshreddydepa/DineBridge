from urllib.parse import quote

from django.conf import settings

from api.db import all_rows, one
from api.errors import DomainError


def _asset_url(key):
    if key and key.startswith("uploaded/"):
        return f"/uploads/{quote(key, safe='/')}"
    base = getattr(settings, "ASSET_BASE_URL", "")
    return f"{base.rstrip('/')}/{quote(key, safe='/')}" if base and key else None


def outlet_config(outlet_id):
    row = one(
        """SELECT o.id, o.tenant_id, o.brand_id, o.slug, o.name, o.address,
                  o.timezone, o.currency, o.ordering_enabled, o.delay_message,
                  o.menu_version, o.active, t.active AS tenant_active, b.active AS brand_active,
                  coalesce(obo.display_name, b.display_name) AS display_name,
                  coalesce(obo.primary_color, b.primary_color) AS primary_color,
                  coalesce(obo.accent_color, b.accent_color) AS accent_color,
                  coalesce(obo.support_email, b.support_email) AS support_email,
                  coalesce(obo.support_phone, b.support_phone) AS support_phone,
                  b.supported_locales,
                  b.presentation || coalesce(obo.presentation, '{}'::jsonb) AS presentation,
                  logo.storage_key AS logo_key, icon.storage_key AS icon_key,
                  hero.storage_key AS hero_key
           FROM outlet o
           JOIN tenant t ON t.id = o.tenant_id
           JOIN brand b ON b.id = o.brand_id
           LEFT JOIN outlet_brand_override obo ON obo.outlet_id = o.id
           LEFT JOIN media_asset logo ON logo.id = coalesce(obo.logo_asset_id, b.logo_asset_id) AND logo.status = 'READY'
           LEFT JOIN media_asset icon ON icon.id = coalesce(obo.icon_asset_id, b.icon_asset_id) AND icon.status = 'READY'
           LEFT JOIN media_asset hero ON hero.id = coalesce(obo.hero_asset_id, b.hero_asset_id) AND hero.status = 'READY'
           WHERE o.id = %s""",
        [outlet_id],
    )
    if not row or not row["tenant_active"] or not row["brand_active"] or not row["active"]:
        raise DomainError("OUTLET_NOT_FOUND", "Outlet not found.", 404)
    for field in ("logo", "icon", "hero"):
        row[f"{field}_url"] = _asset_url(row.pop(f"{field}_key"))
    row.pop("tenant_active")
    row.pop("brand_active")
    return row


def outlet_menu(outlet_id):
    config = outlet_config(outlet_id)
    rows = all_rows(
        """SELECT c.id AS category_id, c.name AS category_name,
                  c.translations AS category_translations, c.display_order AS category_order,
                  mi.id AS item_id, mi.name AS item_name, mi.description,
                  mi.translations AS item_translations, mi.dietary_type, mi.allergens,
                  image.storage_key AS image_key,
                  iv.id AS variant_id, iv.name AS variant_name,
                  iv.display_order AS variant_order,
                  oo.id AS offering_id, oo.price_paise, oo.version,
                  oo.estimate_min_minutes, oo.estimate_max_minutes
           FROM outlet o
           JOIN menu_category c ON c.tenant_id = o.tenant_id AND c.brand_id = o.brand_id AND c.active
           JOIN menu_item mi ON mi.category_id = c.id AND mi.active
           JOIN item_variant iv ON iv.item_id = mi.id AND iv.active
           JOIN outlet_offering oo ON oo.variant_id = iv.id AND oo.outlet_id = o.id
                                  AND oo.active AND oo.available
           LEFT JOIN media_asset image ON image.id = mi.image_asset_id AND image.status = 'READY'
           WHERE o.id = %s
           ORDER BY c.display_order, c.name, mi.name, iv.display_order, iv.name""",
        [outlet_id],
    )
    variants = [row["variant_id"] for row in rows]
    item_ids = list({row["item_id"] for row in rows})
    image_rows = all_rows(
        """SELECT mii.item_id, ma.storage_key
           FROM menu_item_image mii JOIN media_asset ma ON ma.id = mii.asset_id
           WHERE mii.item_id = ANY(%s) AND mii.active AND ma.status = 'READY'
           ORDER BY mii.item_id, mii.display_order, mii.id""",
        [item_ids],
    ) if item_ids else []
    images_by_item = {}
    for image in image_rows:
        images_by_item.setdefault(image["item_id"], []).append(_asset_url(image["storage_key"]))
    modifiers = all_rows(
        """SELECT mg.variant_id, mg.id AS group_id, mg.name AS group_name,
                  mg.min_choices, mg.max_choices, mg.display_order,
                  mo.id AS option_id, mo.name AS option_name, mo.translations,
                  om.price_delta_paise, om.version
           FROM modifier_group mg
           JOIN modifier_option mo ON mo.group_id = mg.id AND mo.active
           JOIN outlet_modifier om ON om.option_id = mo.id AND om.outlet_id = %s AND om.available
           WHERE mg.variant_id = ANY(%s) AND mg.active
           ORDER BY mg.display_order, mg.name, mo.name""",
        [outlet_id, variants],
    ) if variants else []
    groups_by_variant = {}
    for m in modifiers:
        groups = groups_by_variant.setdefault(m["variant_id"], {})
        group = groups.setdefault(m["group_id"], {
            "id": m["group_id"], "name": m["group_name"],
            "min_choices": m["min_choices"], "max_choices": m["max_choices"],
            "options": [],
        })
        group["options"].append({
            "id": m["option_id"], "name": m["option_name"],
            "translations": m["translations"], "price_delta_paise": m["price_delta_paise"],
            "version": m["version"],
        })
    categories = {}
    items = {}
    for row in rows:
        category = categories.setdefault(row["category_id"], {
            "id": row["category_id"], "name": row["category_name"],
            "translations": row["category_translations"], "items": [],
        })
        if row["item_id"] not in items:
            image_urls = images_by_item.get(row["item_id"]) or ([_asset_url(row["image_key"])] if row["image_key"] else [])
            item = {
                "id": row["item_id"], "name": row["item_name"],
                "description": row["description"], "translations": row["item_translations"],
                "dietary_type": row["dietary_type"], "allergens": row["allergens"],
                "image_url": image_urls[0] if image_urls else None,
                "image_urls": image_urls, "variants": [],
            }
            items[row["item_id"]] = item
            category["items"].append(item)
        items[row["item_id"]]["variants"].append({
            "id": row["variant_id"], "name": row["variant_name"],
            "offering_id": row["offering_id"], "price_paise": row["price_paise"],
            "version": row["version"],
            "estimate_min_minutes": row["estimate_min_minutes"],
            "estimate_max_minutes": row["estimate_max_minutes"],
            "modifier_groups": list(groups_by_variant.get(row["variant_id"], {}).values()),
        })
    return {"outlet_id": outlet_id, "menu_version": config["menu_version"],
            "ordering_enabled": config["ordering_enabled"],
            "delay_message": config["delay_message"], "categories": list(categories.values())}
