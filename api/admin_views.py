import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from psycopg.types.json import Jsonb
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.auth import require_outlet_role, require_tenant_role
from api.csrf import require_csrf
from api.db import all_rows, execute, one
from api.errors import DomainError
from api.serializers import (BrandUpdateInput, CategoryInput, ItemInput, QuickItemInput,
                             ModifierGroupInput, ModifierOptionInput, OutletModifierInput,
                             OfferingInput, OfferingUpdateInput,
                             OutletBrandInput, OutletOrderingInput,
                             TableInput, VariantInput)
from api.services import append_event, audit


def _brand(brand_id):
    brand = one("SELECT id, tenant_id FROM brand WHERE id = %s", [brand_id])
    if not brand:
        raise DomainError("BRAND_NOT_FOUND", "Brand not found.", 404)
    return brand


def _outlet(outlet_id):
    outlet = one("SELECT id, tenant_id, brand_id FROM outlet WHERE id = %s", [outlet_id])
    if not outlet:
        raise DomainError("OUTLET_NOT_FOUND", "Outlet not found.", 404)
    return outlet


def _validate_assets(tenant_id, data):
    for field in ("logo_asset_id", "icon_asset_id", "hero_asset_id"):
        asset_id = data.get(field)
        if asset_id and not one("SELECT id FROM media_asset WHERE id = %s AND tenant_id = %s AND status = 'READY'",
                                [asset_id, tenant_id]):
            raise DomainError("INVALID_ASSET", f"{field} must be a ready asset owned by this tenant.", 422)


def _changes(data, allowed):
    fields = [field for field in allowed if field in data]
    if not fields:
        raise DomainError("EMPTY_UPDATE", "Provide at least one field to update.", 422)
    return fields


def _brand_event(brand, actor_id, event_type, entity_type, entity_id):
    outlets = all_rows("SELECT id FROM outlet WHERE brand_id = %s ORDER BY id", [brand["id"]])
    for outlet in outlets:
        execute("UPDATE outlet SET menu_version = menu_version + 1, updated_at = now() WHERE id = %s", [outlet["id"]])
        audit(brand["tenant_id"], outlet["id"], actor_id, event_type, entity_type, entity_id)
        append_event(brand["tenant_id"], outlet["id"], event_type,
                     {"entity_type": entity_type, "entity_id": str(entity_id)})


@api_view(["PATCH"])
@require_csrf
def brand_update(request, brand_id):
    brand = _brand(brand_id)
    user = require_tenant_role(request, brand["tenant_id"], {"OWNER", "MANAGER"})
    serializer = BrandUpdateInput(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    fields = _changes(data, ("display_name", "short_name", "primary_color", "accent_color",
                             "support_email", "support_phone", "logo_asset_id", "icon_asset_id", "hero_asset_id"))
    _validate_assets(brand["tenant_id"], data)
    with transaction.atomic():
        one("SELECT id FROM brand WHERE id = %s FOR UPDATE", [brand_id])
        assignments = ", ".join(f"{field} = %s" for field in fields)
        updated = one(f"UPDATE brand SET {assignments}, updated_at = now() WHERE id = %s RETURNING *",
                      [*(data[field] for field in fields), brand_id])
        _brand_event(brand, user["id"], "brand.updated", "brand", brand_id)
    return Response(updated)


@api_view(["PATCH"])
@require_csrf
def outlet_brand_update(request, outlet_id):
    outlet = _outlet(outlet_id)
    user, _ = require_outlet_role(request, outlet_id, {"OWNER", "MANAGER"})
    serializer = OutletBrandInput(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    fields = _changes(data, ("display_name", "primary_color", "accent_color", "support_email",
                             "support_phone", "logo_asset_id", "icon_asset_id", "hero_asset_id"))
    _validate_assets(outlet["tenant_id"], data)
    with transaction.atomic():
        one("SELECT id FROM outlet WHERE id = %s FOR UPDATE", [outlet_id])
        execute("""INSERT INTO outlet_brand_override(tenant_id, outlet_id)
                   VALUES (%s, %s) ON CONFLICT (outlet_id) DO NOTHING""",
                [outlet["tenant_id"], outlet_id])
        assignments = ", ".join(f"{field} = %s" for field in fields)
        updated = one(f"""UPDATE outlet_brand_override SET {assignments}, updated_at = now()
                          WHERE outlet_id = %s RETURNING *""",
                      [*(data[field] for field in fields), outlet_id])
        audit(outlet["tenant_id"], outlet_id, user["id"], "outlet.brand_updated", "outlet", outlet_id)
        append_event(outlet["tenant_id"], outlet_id, "outlet.brand_updated", {"outlet_id": str(outlet_id)})
    return Response(updated)


@api_view(["PATCH"])
@require_csrf
def outlet_ordering_update(request, outlet_id):
    outlet = _outlet(outlet_id)
    user, _ = require_outlet_role(request, outlet_id, {"OWNER", "MANAGER"})
    serializer = OutletOrderingInput(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    fields = _changes(data, ("ordering_enabled", "delay_message"))
    with transaction.atomic():
        assignments = ", ".join(f"{field} = %s" for field in fields)
        updated = one(f"""UPDATE outlet SET {assignments}, menu_version = menu_version + 1,
                         updated_at = now() WHERE id = %s RETURNING id, ordering_enabled,
                         delay_message, menu_version""",
                      [*(data[field] for field in fields), outlet_id])
        audit(outlet["tenant_id"], outlet_id, user["id"], "outlet.ordering_updated", "outlet", outlet_id)
        append_event(outlet["tenant_id"], outlet_id, "outlet.ordering_updated", {"outlet_id": str(outlet_id)})
    return Response(updated)


@api_view(["POST"])
@require_csrf
def category_create(request, brand_id):
    brand = _brand(brand_id)
    user = require_tenant_role(request, brand["tenant_id"], {"OWNER", "MANAGER"})
    serializer = CategoryInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        created = one("""INSERT INTO menu_category(tenant_id, brand_id, name, display_order)
                         VALUES (%s, %s, %s, %s) RETURNING id, name, display_order""",
                      [brand["tenant_id"], brand_id, data["name"], data["display_order"]])
        _brand_event(brand, user["id"], "catalogue.category_created", "menu_category", created["id"])
    return Response(created, status=201)


@api_view(["POST"])
@require_csrf
def item_create(request, brand_id):
    brand = _brand(brand_id)
    user = require_tenant_role(request, brand["tenant_id"], {"OWNER", "MANAGER"})
    serializer = ItemInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if not one("SELECT id FROM menu_category WHERE id = %s AND brand_id = %s AND active",
               [data["category_id"], brand_id]):
        raise DomainError("INVALID_CATEGORY", "Category does not belong to this brand.", 422)
    with transaction.atomic():
        created = one("""INSERT INTO menu_item(tenant_id, brand_id, category_id, name,
                                               description, dietary_type, allergens)
                         VALUES (%s, %s, %s, %s, %s, %s, %s)
                         RETURNING id, name, dietary_type""",
                      [brand["tenant_id"], brand_id, data["category_id"], data["name"],
                       data["description"], data["dietary_type"], Jsonb(data["allergens"])])
        _brand_event(brand, user["id"], "catalogue.item_created", "menu_item", created["id"])
    return Response(created, status=201)


@api_view(["POST"])
@require_csrf
def quick_item_create(request, outlet_id):
    outlet = _outlet(outlet_id)
    user = require_tenant_role(request, outlet["tenant_id"], {"OWNER", "MANAGER"})
    serializer = QuickItemInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if not one("SELECT id FROM menu_category WHERE id = %s AND brand_id = %s AND active",
               [data["category_id"], outlet["brand_id"]]):
        raise DomainError("INVALID_CATEGORY", "Category does not belong to this outlet's brand.", 422)
    with transaction.atomic():
        item = one("""INSERT INTO menu_item(tenant_id, brand_id, category_id, name,
                                              description, dietary_type, allergens)
                      VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, name""",
                   [outlet["tenant_id"], outlet["brand_id"], data["category_id"], data["name"],
                    data["description"], data["dietary_type"], Jsonb(data["allergens"])])
        variant = one("""INSERT INTO item_variant(tenant_id, brand_id, item_id, name)
                         VALUES (%s, %s, %s, 'Regular') RETURNING id""",
                      [outlet["tenant_id"], outlet["brand_id"], item["id"]])
        offering = one("""INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id,
                                                      price_paise, estimate_max_minutes)
                          VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, version""",
                       [outlet["tenant_id"], outlet["brand_id"], outlet_id, variant["id"],
                        data["price_paise"], data["estimate_max_minutes"]])
        _brand_event({"id": outlet["brand_id"], "tenant_id": outlet["tenant_id"]}, user["id"],
                     "catalogue.item_created", "menu_item", item["id"])
    return Response({"item": item, "variant": variant, "offering": offering}, status=201)


@api_view(["POST"])
@require_csrf
def variant_create(request, item_id):
    item = one("SELECT id, tenant_id, brand_id FROM menu_item WHERE id = %s AND active", [item_id])
    if not item:
        raise DomainError("ITEM_NOT_FOUND", "Menu item not found.", 404)
    user = require_tenant_role(request, item["tenant_id"], {"OWNER", "MANAGER"})
    serializer = VariantInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        created = one("""INSERT INTO item_variant(tenant_id, brand_id, item_id, name, display_order)
                         VALUES (%s, %s, %s, %s, %s) RETURNING id, name, display_order""",
                      [item["tenant_id"], item["brand_id"], item_id, data["name"], data["display_order"]])
        _brand_event({"id": item["brand_id"], "tenant_id": item["tenant_id"]}, user["id"],
                     "catalogue.variant_created", "item_variant", created["id"])
    return Response(created, status=201)


@api_view(["POST"])
@require_csrf
def modifier_group_create(request, variant_id):
    variant = one("SELECT id, tenant_id, brand_id FROM item_variant WHERE id = %s AND active", [variant_id])
    if not variant:
        raise DomainError("VARIANT_NOT_FOUND", "Variant not found.", 404)
    user = require_tenant_role(request, variant["tenant_id"], {"OWNER", "MANAGER"})
    serializer = ModifierGroupInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        created = one("""INSERT INTO modifier_group(tenant_id, brand_id, variant_id,
                                                    name, min_choices, max_choices, display_order)
                         VALUES (%s, %s, %s, %s, %s, %s, %s)
                         RETURNING id, name, min_choices, max_choices, display_order""",
                      [variant["tenant_id"], variant["brand_id"], variant_id, data["name"],
                       data["min_choices"], data["max_choices"], data["display_order"]])
        _brand_event({"id": variant["brand_id"], "tenant_id": variant["tenant_id"]}, user["id"],
                     "catalogue.modifier_group_created", "modifier_group", created["id"])
    return Response(created, status=201)


@api_view(["POST"])
@require_csrf
def modifier_option_create(request, group_id):
    group = one("SELECT id, tenant_id, brand_id FROM modifier_group WHERE id = %s AND active", [group_id])
    if not group:
        raise DomainError("GROUP_NOT_FOUND", "Modifier group not found.", 404)
    user = require_tenant_role(request, group["tenant_id"], {"OWNER", "MANAGER"})
    serializer = ModifierOptionInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        created = one("""INSERT INTO modifier_option(tenant_id, brand_id, group_id, name)
                         VALUES (%s, %s, %s, %s) RETURNING id, name""",
                      [group["tenant_id"], group["brand_id"], group_id, serializer.validated_data["name"]])
        _brand_event({"id": group["brand_id"], "tenant_id": group["tenant_id"]}, user["id"],
                     "catalogue.modifier_option_created", "modifier_option", created["id"])
    return Response(created, status=201)


@api_view(["POST"])
@require_csrf
def outlet_modifier_create(request, outlet_id):
    outlet = _outlet(outlet_id)
    user, _ = require_outlet_role(request, outlet_id, {"OWNER", "MANAGER"})
    serializer = OutletModifierInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if not one("SELECT id FROM modifier_option WHERE id = %s AND tenant_id = %s AND brand_id = %s AND active",
               [data["option_id"], outlet["tenant_id"], outlet["brand_id"]]):
        raise DomainError("INVALID_OPTION", "Option does not belong to this outlet's brand.", 422)
    with transaction.atomic():
        created = one("""INSERT INTO outlet_modifier(tenant_id, brand_id, outlet_id,
                                                     option_id, price_delta_paise, available)
                         VALUES (%s, %s, %s, %s, %s, %s)
                         RETURNING id, option_id, price_delta_paise, available, version""",
                      [outlet["tenant_id"], outlet["brand_id"], outlet_id, data["option_id"],
                       data["price_delta_paise"], data["available"]])
        execute("UPDATE outlet SET menu_version = menu_version + 1 WHERE id = %s", [outlet_id])
        audit(outlet["tenant_id"], outlet_id, user["id"], "outlet_modifier.created", "outlet_modifier", created["id"])
        append_event(outlet["tenant_id"], outlet_id, "outlet_modifier.created",
                     {"outlet_modifier_id": str(created["id"])})
    return Response(created, status=201)


@api_view(["POST"])
@require_csrf
def offering_create(request, outlet_id):
    outlet = _outlet(outlet_id)
    user, _ = require_outlet_role(request, outlet_id, {"OWNER", "MANAGER"})
    serializer = OfferingInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if not one("SELECT id FROM item_variant WHERE id = %s AND tenant_id = %s AND brand_id = %s AND active",
               [data["variant_id"], outlet["tenant_id"], outlet["brand_id"]]):
        raise DomainError("INVALID_VARIANT", "Variant does not belong to this outlet's brand.", 422)
    with transaction.atomic():
        created = one("""INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id,
                                                     price_paise, estimate_min_minutes,
                                                     estimate_max_minutes, available)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                         RETURNING id, variant_id, price_paise, available, version""",
                      [outlet["tenant_id"], outlet["brand_id"], outlet_id, data["variant_id"],
                       data["price_paise"], data["estimate_min_minutes"],
                       data["estimate_max_minutes"], data["available"]])
        execute("UPDATE outlet SET menu_version = menu_version + 1 WHERE id = %s", [outlet_id])
        audit(outlet["tenant_id"], outlet_id, user["id"], "offering.created", "outlet_offering", created["id"])
        append_event(outlet["tenant_id"], outlet_id, "offering.created", {"offering_id": str(created["id"])})
    return Response(created, status=201)


@api_view(["PATCH"])
@require_csrf
def offering_update(request, outlet_id, offering_id):
    outlet = _outlet(outlet_id)
    user, _ = require_outlet_role(request, outlet_id, {"OWNER", "MANAGER"})
    serializer = OfferingUpdateInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    fields = _changes(data, ("price_paise", "estimate_min_minutes", "estimate_max_minutes", "available", "active"))
    with transaction.atomic():
        one("SELECT id FROM outlet WHERE id = %s FOR UPDATE", [outlet_id])
        offering = one("SELECT * FROM outlet_offering WHERE id = %s AND outlet_id = %s FOR UPDATE", [offering_id, outlet_id])
        if not offering:
            raise DomainError("OFFERING_NOT_FOUND", "Offering not found.", 404)
        if offering["version"] != data["expected_version"]:
            raise DomainError("REVISION_CONFLICT", "Refresh the offering before editing.", 409,
                              {"version": offering["version"]})
        lower = data.get("estimate_min_minutes", offering["estimate_min_minutes"])
        upper = data.get("estimate_max_minutes", offering["estimate_max_minutes"])
        if upper < lower:
            raise DomainError("INVALID_ESTIMATE", "Maximum estimate must be at least the minimum.", 422)
        assignments = ", ".join(f"{field} = %s" for field in fields)
        updated = one(f"""UPDATE outlet_offering SET {assignments}, version = version + 1,
                         updated_at = now() WHERE id = %s
                         RETURNING id, price_paise, available, active, estimate_min_minutes,
                                   estimate_max_minutes, version""",
                      [*(data[field] for field in fields), offering_id])
        execute("UPDATE outlet SET menu_version = menu_version + 1 WHERE id = %s", [outlet_id])
        audit(outlet["tenant_id"], outlet_id, user["id"], "offering.updated", "outlet_offering", offering_id,
              before={"version": offering["version"]}, after={"version": updated["version"]})
        append_event(outlet["tenant_id"], outlet_id, "offering.updated", {"offering_id": str(offering_id)})
    return Response(updated)


def create_table(request, outlet_id):
    outlet = _outlet(outlet_id)
    user, _ = require_outlet_role(request, outlet_id, {"OWNER", "MANAGER"})
    serializer = TableInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        created = one("""INSERT INTO dining_table(tenant_id, outlet_id, label, qr_token_hash)
                         VALUES (%s, %s, %s, %s) RETURNING id, label""",
                      [outlet["tenant_id"], outlet_id, serializer.validated_data["label"],
                       hashlib.sha256(raw.encode()).digest()])
        audit(outlet["tenant_id"], outlet_id, user["id"], "table.created", "dining_table", created["id"])
    qr_base = settings.QR_PUBLIC_BASE_URL or request.build_absolute_uri("/").rstrip("/")
    return Response({**created, "qr_url": f"{qr_base}/q/{raw}"}, status=201)


@api_view(["POST"])
@require_csrf
def table_rotate_qr(request, table_id):
    target = one("SELECT id, tenant_id, outlet_id FROM dining_table WHERE id = %s", [table_id])
    if not target:
        raise DomainError("TABLE_NOT_FOUND", "Table not found.", 404)
    user, _ = require_outlet_role(request, target["outlet_id"], {"OWNER", "MANAGER"})
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        one("SELECT id FROM dining_table WHERE id = %s FOR UPDATE", [table_id])
        execute("UPDATE dining_table SET qr_token_hash = %s, qr_rotated_at = now(), updated_at = now() WHERE id = %s",
                [hashlib.sha256(raw.encode()).digest(), table_id])
        execute("UPDATE browser_access SET revoked_at = now() WHERE table_id = %s AND revoked_at IS NULL", [table_id])
        audit(target["tenant_id"], target["outlet_id"], user["id"], "table.qr_rotated", "dining_table", table_id)
        append_event(target["tenant_id"], target["outlet_id"], "table.qr_rotated", {"table_id": str(table_id)})
    qr_base = settings.QR_PUBLIC_BASE_URL or request.build_absolute_uri("/").rstrip("/")
    return Response({"table_id": table_id, "qr_url": f"{qr_base}/q/{raw}"})
