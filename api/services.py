import hashlib
import json
import secrets
from collections import Counter

from django.db import transaction
from django.utils import timezone
from psycopg.types.json import Jsonb

from api.auth import access_expiry
from api.db import all_rows, execute, one
from api.errors import DomainError


def append_event(tenant_id, outlet_id, event_type, payload, visit_id=None):
    # Take this lock last. Holding it until commit makes IDs commit-ordered per outlet.
    one("SELECT outlet_id FROM outlet_event_mutex WHERE outlet_id = %s FOR UPDATE", [outlet_id])
    event = one(
        """INSERT INTO domain_event(tenant_id, outlet_id, visit_id, event_type, payload)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        [tenant_id, outlet_id, visit_id, event_type, Jsonb(payload)],
    )
    execute("INSERT INTO outbox_entry(event_id) VALUES (%s)", [event["id"]])
    return event["id"]


def audit(tenant_id, outlet_id, actor_id, action, entity_type, entity_id, reason=None, before=None, after=None):
    execute(
        """INSERT INTO audit_event(tenant_id, outlet_id, actor_id, action, entity_type,
                                   entity_id, reason, before_state, after_state)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        [tenant_id, outlet_id, actor_id, action, entity_type, entity_id, reason,
         Jsonb(before) if before is not None else None,
         Jsonb(after) if after is not None else None],
    )


def bootstrap_access(qr_token):
    try:
        token_hash = hashlib.sha256(qr_token.encode("ascii")).digest()
    except UnicodeEncodeError as exc:
        raise DomainError("QR_INVALID", "Invalid table QR code.", 404) from exc
    with transaction.atomic():
        table = one(
            """SELECT dt.id, dt.tenant_id, dt.outlet_id, dt.label, dt.next_visit_number,
                      o.ordering_enabled, o.active AS outlet_active,
                      b.active AS brand_active, t.active AS tenant_active
               FROM dining_table dt
               JOIN outlet o ON o.id = dt.outlet_id
               JOIN brand b ON b.id = o.brand_id
               JOIN tenant t ON t.id = o.tenant_id
               WHERE dt.qr_token_hash = %s AND dt.active FOR UPDATE OF dt""",
            [token_hash],
        )
        if not table or not all(table[k] for k in ("outlet_active", "brand_active", "tenant_active")):
            raise DomainError("QR_INVALID", "Invalid table QR code.", 404)
        visit = one(
            "SELECT id FROM dining_visit WHERE table_id = %s AND status IN ('OPEN','CHECKOUT')",
            [table["id"]],
        )
        raw = secrets.token_urlsafe(32)
        access = one(
            """INSERT INTO browser_access(tenant_id, outlet_id, table_id, visit_id,
                                          expected_visit_number, token_hash, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            [table["tenant_id"], table["outlet_id"], table["id"],
             visit["id"] if visit else None, table["next_visit_number"],
             hashlib.sha256(raw.encode("ascii")).digest(), access_expiry()],
        )
    return raw, {"access_id": access["id"], "outlet_id": table["outlet_id"], "table_label": table["label"]}


def _canonical_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).digest()


def _selected_modifiers(outlet_id, variant_id, option_ids):
    groups = all_rows(
        """SELECT id, name, min_choices, max_choices FROM modifier_group
           WHERE variant_id = %s AND active ORDER BY id""",
        [variant_id],
    )
    selected = all_rows(
        """SELECT om.id AS outlet_modifier_id, om.option_id, om.price_delta_paise,
                  mo.name AS option_name, mg.id AS group_id, mg.name AS group_name
           FROM outlet_modifier om
           JOIN modifier_option mo ON mo.id = om.option_id AND mo.active
           JOIN modifier_group mg ON mg.id = mo.group_id AND mg.active
           WHERE om.outlet_id = %s AND om.option_id = ANY(%s)
             AND om.available AND mg.variant_id = %s
           ORDER BY om.id FOR UPDATE OF om""",
        [outlet_id, option_ids, variant_id],
    ) if option_ids else []
    if len(selected) != len(option_ids):
        raise DomainError("INVALID_MODIFIERS", "An option is unavailable or belongs to another item.", 422)
    counts = Counter(row["group_id"] for row in selected)
    for group in groups:
        count = counts[group["id"]]
        if not group["min_choices"] <= count <= group["max_choices"]:
            raise DomainError("INVALID_MODIFIERS", f"Choose {group['min_choices']} to {group['max_choices']} options for {group['name']}.", 422)
    return selected


def place_order(access, payload, idempotency_key):
    if not 8 <= len(idempotency_key) <= 200:
        raise DomainError("IDEMPOTENCY_KEY_REQUIRED", "Provide an Idempotency-Key header of 8 to 200 characters.", 400)
    request_hash = _canonical_hash(payload)
    with transaction.atomic():
        table = one(
            """SELECT dt.*, o.brand_id, o.ordering_enabled, o.active AS outlet_active,
                      b.active AS brand_active, t.active AS tenant_active
               FROM dining_table dt JOIN outlet o ON o.id = dt.outlet_id
               JOIN brand b ON b.id = o.brand_id JOIN tenant t ON t.id = o.tenant_id
               WHERE dt.id = %s FOR UPDATE OF dt FOR SHARE OF o""",
            [access["table_id"]],
        )
        current = one(
            "SELECT id, request_hash, browser_access_id FROM orders WHERE outlet_id = %s AND idempotency_key = %s",
            [access["outlet_id"], idempotency_key],
        )
        if current:
            if current["browser_access_id"] != access["id"] or bytes(current["request_hash"]) != request_hash:
                raise DomainError("IDEMPOTENCY_CONFLICT", "That key belongs to a different order.", 409)
            return current["id"], False
        locked_access = one("SELECT * FROM browser_access WHERE id = %s FOR UPDATE", [access["id"]])
        if not locked_access or locked_access["revoked_at"] or locked_access["expires_at"] <= timezone.now():
            raise DomainError("ACCESS_EXPIRED", "Scan the table QR code again.", 401)
        if table["next_visit_number"] != locked_access["expected_visit_number"]:
            raise DomainError("VISIT_CLOSED", "This table visit has ended. Scan the QR code again.", 409)
        if not table["active"] or not all(table[k] for k in ("outlet_active", "brand_active", "tenant_active")) or not table["ordering_enabled"]:
            raise DomainError("ORDERING_PAUSED", "Ordering is unavailable for this outlet.", 409)
        visit = one("SELECT id, status FROM dining_visit WHERE table_id = %s AND status IN ('OPEN','CHECKOUT')", [table["id"]])
        if visit and visit["status"] == "CHECKOUT":
            raise DomainError("VISIT_IN_CHECKOUT", "Billing has started for this table.", 409)
        if locked_access["visit_id"] and (not visit or locked_access["visit_id"] != visit["id"]):
            raise DomainError("VISIT_CLOSED", "This table visit has ended. Scan the QR code again.", 409)

        validated = []
        subtotal = 0
        for line in sorted(payload["lines"], key=lambda value: str(value["offering_id"])):
            offer = one(
                """SELECT oo.id, oo.variant_id, oo.price_paise, oo.version,
                          oo.estimate_min_minutes, oo.estimate_max_minutes,
                          oo.active, oo.available,
                          iv.name AS variant_name, iv.active AS variant_active,
                          mi.name AS item_name, mi.dietary_type, mi.allergens,
                          mi.active AS item_active, c.active AS category_active
                   FROM outlet_offering oo
                   JOIN item_variant iv ON iv.id = oo.variant_id
                   JOIN menu_item mi ON mi.id = iv.item_id
                   JOIN menu_category c ON c.id = mi.category_id
                   WHERE oo.id = %s AND oo.outlet_id = %s FOR UPDATE OF oo""",
                [line["offering_id"], table["outlet_id"]],
            )
            if not offer or not all(offer[k] for k in ("active", "available", "variant_active", "item_active", "category_active")):
                raise DomainError("ITEM_UNAVAILABLE", "An item is no longer available.", 409)
            if offer["version"] != line["expected_version"] or offer["price_paise"] != line["expected_price_paise"]:
                raise DomainError("PRICE_CHANGED", "Review the updated menu price before ordering.", 409,
                                  {"offering_id": str(offer["id"]), "price_paise": offer["price_paise"], "version": offer["version"]})
            selected = _selected_modifiers(table["outlet_id"], offer["variant_id"], line["option_ids"])
            modifier_price = sum(option["price_delta_paise"] for option in selected)
            subtotal += (offer["price_paise"] + modifier_price) * line["quantity"]
            validated.append((line, offer, selected, modifier_price))

        if not visit:
            visit = one(
                """INSERT INTO dining_visit(tenant_id, outlet_id, table_id, visit_number)
                   VALUES (%s, %s, %s, %s) RETURNING id, status""",
                [table["tenant_id"], table["outlet_id"], table["id"], table["next_visit_number"]],
            )
        if locked_access["visit_id"] is None:
            execute("UPDATE browser_access SET visit_id = %s, last_used_at = now() WHERE id = %s",
                    [visit["id"], locked_access["id"]])
        else:
            execute("UPDATE browser_access SET last_used_at = now() WHERE id = %s", [locked_access["id"]])
        next_ref = one("SELECT count(*) + 1 AS n FROM orders WHERE visit_id = %s", [visit["id"]])["n"]
        display_ref = f"{table['label']}-{table['next_visit_number']}-{next_ref}"
        order = one(
            """INSERT INTO orders(tenant_id, outlet_id, visit_id, browser_access_id, source,
                                  display_ref, idempotency_key, request_hash, subtotal_paise)
               VALUES (%s, %s, %s, %s, 'CUSTOMER', %s, %s, %s, %s) RETURNING id""",
            [table["tenant_id"], table["outlet_id"], visit["id"], access["id"],
             display_ref, idempotency_key, request_hash, subtotal],
        )
        for line, offer, selected, modifier_price in validated:
            saved_line = one(
                """INSERT INTO order_line(tenant_id, outlet_id, order_id, offering_id,
                                          item_name_snapshot, variant_name_snapshot,
                                          dietary_type_snapshot, allergens_snapshot,
                                          base_unit_paise, modifier_unit_paise,
                                          quantity, queued_qty, notes,
                                          estimate_min_minutes_snapshot, estimate_max_minutes_snapshot)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                [table["tenant_id"], table["outlet_id"], order["id"], offer["id"],
                 offer["item_name"], offer["variant_name"], offer["dietary_type"], Jsonb(offer["allergens"]),
                 offer["price_paise"], modifier_price, line["quantity"], line["quantity"], line["notes"],
                 offer["estimate_min_minutes"], offer["estimate_max_minutes"]],
            )
            for option in selected:
                execute(
                    """INSERT INTO line_modifier(tenant_id, outlet_id, line_id, outlet_modifier_id,
                                                 group_name_snapshot, option_name_snapshot, delta_paise_snapshot)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    [table["tenant_id"], table["outlet_id"], saved_line["id"], option["outlet_modifier_id"],
                     option["group_name"], option["option_name"], option["price_delta_paise"]],
                )
        append_event(table["tenant_id"], table["outlet_id"], "order.placed",
                     {"order_id": str(order["id"]), "display_ref": display_ref, "table_id": str(table["id"])}, visit["id"])
        return order["id"], True


def order_snapshot(order_id):
    order = one(
        """SELECT id, outlet_id, visit_id, browser_access_id, source, display_ref,
                  subtotal_paise, placed_at, seen_at FROM orders WHERE id = %s""",
        [order_id],
    )
    if not order:
        raise DomainError("ORDER_NOT_FOUND", "Order not found.", 404)
    lines = all_rows(
        """SELECT id, item_name_snapshot AS item_name, variant_name_snapshot AS variant_name,
                  dietary_type_snapshot AS dietary_type, allergens_snapshot AS allergens,
                  base_unit_paise, modifier_unit_paise, quantity, queued_qty, preparing_qty,
                  ready_qty, served_qty, cancelled_qty, notes,
                  estimate_min_minutes_snapshot AS estimate_min_minutes,
                  estimate_max_minutes_snapshot AS estimate_max_minutes, revision
           FROM order_line WHERE order_id = %s ORDER BY created_at, id""",
        [order_id],
    )
    modifiers = all_rows(
        """SELECT lm.line_id, lm.group_name_snapshot AS group_name,
                  lm.option_name_snapshot AS option_name, lm.delta_paise_snapshot AS delta_paise
           FROM line_modifier lm JOIN order_line ol ON ol.id = lm.line_id
           WHERE ol.order_id = %s ORDER BY lm.id""",
        [order_id],
    )
    by_line = {line["id"]: line for line in lines}
    for line in lines:
        line["modifiers"] = []
    for modifier in modifiers:
        by_line[modifier.pop("line_id")]["modifiers"].append(modifier)
    order.pop("browser_access_id")
    order["lines"] = lines
    return order
