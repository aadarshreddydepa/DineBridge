from django.db import transaction

from api.db import all_rows, execute, one
from api.errors import DomainError
from api.services import append_event, audit


def _locked_visit(visit_id):
    target = one("SELECT tenant_id, outlet_id, table_id FROM dining_visit WHERE id = %s", [visit_id])
    if not target:
        raise DomainError("VISIT_NOT_FOUND", "Visit not found.", 404)
    table = one("SELECT id, next_visit_number FROM dining_table WHERE id = %s FOR UPDATE", [target["table_id"]])
    visit = one("SELECT * FROM dining_visit WHERE id = %s FOR UPDATE", [visit_id])
    return target, table, visit


def tables_snapshot(outlet_id):
    snapshot = one(
        """SELECT (SELECT coalesce(max(id), 0) FROM domain_event WHERE outlet_id = %s) AS cursor,
                  coalesce((
                    SELECT jsonb_agg(to_jsonb(t) ORDER BY t.label)
                    FROM (
                      SELECT dt.id, dt.label, dt.seating_capacity, dt.active, dv.id AS visit_id, dv.status,
                             dv.started_at, dv.checkout_at,
                             count(DISTINCT o.id) FILTER (WHERE o.seen_at IS NULL) AS unseen_orders,
                             count(DISTINCT sr.id) FILTER (WHERE sr.status = 'OPEN') AS open_requests
                      FROM dining_table dt
                      LEFT JOIN dining_visit dv ON dv.table_id = dt.id AND dv.status IN ('OPEN','CHECKOUT')
                      LEFT JOIN orders o ON o.visit_id = dv.id
                      LEFT JOIN service_request sr ON sr.visit_id = dv.id
                      WHERE dt.outlet_id = %s AND dt.active GROUP BY dt.id, dv.id
                    ) t
                  ), '[]'::jsonb) AS tables""",
        [outlet_id, outlet_id],
    )
    return {"outlet_id": outlet_id, **snapshot}


def kitchen_queue(outlet_id):
    lines = all_rows(
        """SELECT dt.id AS table_id, dt.label AS table_label,
                  dv.id AS visit_id, o.id AS order_id, o.display_ref, o.placed_at,
                  ol.id AS line_id, ol.item_name_snapshot AS item_name,
                  ol.variant_name_snapshot AS variant_name,
                  ol.notes, ol.quantity, ol.queued_qty, ol.preparing_qty,
                  ol.ready_qty, ol.served_qty, ol.cancelled_qty, ol.revision
           FROM order_line ol JOIN orders o ON o.id = ol.order_id
           JOIN dining_visit dv ON dv.id = o.visit_id
           JOIN dining_table dt ON dt.id = dv.table_id
           WHERE o.outlet_id = %s AND dv.status IN ('OPEN','CHECKOUT')
             AND (ol.queued_qty + ol.preparing_qty + ol.ready_qty) > 0
           ORDER BY o.placed_at, o.id, ol.created_at, ol.id""",
        [outlet_id],
    )
    line_ids = [row["line_id"] for row in lines]
    modifiers = all_rows(
        """SELECT line_id, group_name_snapshot AS group_name,
                  option_name_snapshot AS option_name FROM line_modifier
           WHERE line_id = ANY(%s) ORDER BY line_id, id""",
        [line_ids],
    ) if line_ids else []
    by_line = {row["line_id"]: row for row in lines}
    for row in lines:
        row["modifiers"] = []
    for modifier in modifiers:
        by_line[modifier.pop("line_id")]["modifiers"].append(modifier)
    return lines


def mark_seen(order_id, actor_id):
    with transaction.atomic():
        order = one("SELECT id, tenant_id, outlet_id, visit_id, seen_at FROM orders WHERE id = %s FOR UPDATE", [order_id])
        if not order:
            raise DomainError("ORDER_NOT_FOUND", "Order not found.", 404)
        if order["seen_at"] is None:
            execute("UPDATE orders SET seen_at = now(), seen_by_id = %s WHERE id = %s", [actor_id, order_id])
            audit(order["tenant_id"], order["outlet_id"], actor_id, "order.seen", "order", order_id)
        return order["outlet_id"]


def progress_line(line_id, actor_id, to_state, quantity, expected_revision, reason, from_state=None):
    target = one(
        """SELECT ol.tenant_id, ol.outlet_id, o.visit_id, dv.table_id
           FROM order_line ol JOIN orders o ON o.id = ol.order_id
           JOIN dining_visit dv ON dv.id = o.visit_id WHERE ol.id = %s""",
        [line_id],
    )
    if not target:
        raise DomainError("LINE_NOT_FOUND", "Order line not found.", 404)
    with transaction.atomic():
        one("SELECT id FROM dining_table WHERE id = %s FOR UPDATE", [target["table_id"]])
        visit = one("SELECT status FROM dining_visit WHERE id = %s", [target["visit_id"]])
        if visit["status"] == "CLOSED":
            raise DomainError("VISIT_CLOSED", "This visit is closed.", 409)
        line = one("SELECT * FROM order_line WHERE id = %s FOR UPDATE", [line_id])
        if line["revision"] != expected_revision:
            raise DomainError("REVISION_CONFLICT", "Refresh the line and try again.", 409, {"revision": line["revision"]})
        transition = {
            "PREPARING": ("QUEUED", "queued_qty", "preparing_qty"),
            "READY": ("PREPARING", "preparing_qty", "ready_qty"),
            "SERVED": ("READY", "ready_qty", "served_qty"),
        }
        if to_state == "CANCELLED":
            if not reason.strip():
                raise DomainError("REASON_REQUIRED", "Cancellation requires a reason.", 422)
            source = from_state
            if source not in {"QUEUED", "PREPARING", "READY"}:
                raise DomainError("INVALID_PROGRESS", "Choose the state to cancel from.", 422)
            from_col = source.lower() + "_qty"
            to_col = "cancelled_qty"
        else:
            source, from_col, to_col = transition[to_state]
        if line[from_col] < quantity:
            raise DomainError("INVALID_PROGRESS", "Not enough units in the source state.", 409)
        # Column names come exclusively from the fixed transition map above.
        execute(
            f"""UPDATE order_line SET {from_col} = {from_col} - %s,
                    {to_col} = {to_col} + %s, revision = revision + 1,
                    ready_at = CASE WHEN %s = 'READY' AND ready_at IS NULL THEN now() ELSE ready_at END,
                    served_at = CASE WHEN %s = 'SERVED' AND served_at IS NULL THEN now() ELSE served_at END,
                    updated_at = now() WHERE id = %s""",
            [quantity, quantity, to_state, to_state, line_id],
        )
        execute(
            """INSERT INTO line_progress_event(tenant_id, outlet_id, line_id, from_state,
                                               to_state, quantity, line_revision, actor_id, reason)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [target["tenant_id"], target["outlet_id"], line_id, source, to_state,
             quantity, line["revision"] + 1, actor_id, reason or None],
        )
        audit(target["tenant_id"], target["outlet_id"], actor_id, "line.progress", "order_line", line_id,
              reason=reason or None, before={"revision": line["revision"]}, after={"revision": line["revision"] + 1, "to_state": to_state, "quantity": quantity})
        append_event(target["tenant_id"], target["outlet_id"], "line.progress",
                     {"line_id": str(line_id), "to_state": to_state, "quantity": quantity}, target["visit_id"])
    return one("SELECT queued_qty, preparing_qty, ready_qty, served_qty, cancelled_qty, revision FROM order_line WHERE id = %s", [line_id])


def start_checkout(visit_id, actor_id):
    with transaction.atomic():
        target, table, visit = _locked_visit(visit_id)
        if visit["status"] == "CLOSED":
            raise DomainError("VISIT_CLOSED", "This visit is closed.", 409)
        if visit["status"] == "OPEN":
            execute("UPDATE dining_visit SET status = 'CHECKOUT', checkout_at = now(), revision = revision + 1 WHERE id = %s", [visit_id])
            audit(target["tenant_id"], target["outlet_id"], actor_id, "visit.checkout", "dining_visit", visit_id)
            append_event(target["tenant_id"], target["outlet_id"], "visit.checkout", {"visit_id": str(visit_id)}, visit_id)
    return reconciliation(visit_id)


def cancel_checkout(visit_id, actor_id):
    with transaction.atomic():
        target, table, visit = _locked_visit(visit_id)
        if visit["status"] != "CHECKOUT":
            raise DomainError("INVALID_VISIT_STATE", "Only checkout visits can return to ordering.", 409)
        execute("UPDATE dining_visit SET status = 'OPEN', checkout_at = NULL, revision = revision + 1 WHERE id = %s", [visit_id])
        audit(target["tenant_id"], target["outlet_id"], actor_id, "visit.checkout_cancelled", "dining_visit", visit_id)
        append_event(target["tenant_id"], target["outlet_id"], "visit.checkout_cancelled", {"visit_id": str(visit_id)}, visit_id)
    return reconciliation(visit_id)


def reconciliation(visit_id):
    visit = one("SELECT id, outlet_id, table_id, status, visit_number FROM dining_visit WHERE id = %s", [visit_id])
    if not visit:
        raise DomainError("VISIT_NOT_FOUND", "Visit not found.", 404)
    totals = one(
        """SELECT coalesce(sum(o.subtotal_paise), 0) AS submitted_subtotal_paise,
                  coalesce(sum(lines.effective_paise), 0) AS effective_subtotal_paise,
                  count(o.id) AS order_count
           FROM orders o LEFT JOIN LATERAL (
             SELECT sum((ol.base_unit_paise + ol.modifier_unit_paise) *
                        (ol.quantity - ol.cancelled_qty)) AS effective_paise
             FROM order_line ol WHERE ol.order_id = o.id
           ) lines ON true WHERE o.visit_id = %s""",
        [visit_id],
    )
    outstanding = one(
        """SELECT coalesce(sum(ol.queued_qty + ol.preparing_qty + ol.ready_qty), 0) AS units,
                  (SELECT count(*) FROM service_request WHERE visit_id = %s AND status = 'OPEN') AS requests
           FROM order_line ol JOIN orders o ON o.id = ol.order_id WHERE o.visit_id = %s""",
        [visit_id, visit_id],
    )
    return {**visit, **totals, "outstanding_units": outstanding["units"],
            "open_service_requests": outstanding["requests"]}


def complete_billing(visit_id, actor_id, billing):
    with transaction.atomic():
        target, table, visit = _locked_visit(visit_id)
        if visit["status"] == "CLOSED":
            closure = one("SELECT * FROM closure_record WHERE visit_id = %s", [visit_id])
            return closure, False
        if visit["status"] != "CHECKOUT":
            raise DomainError("INVALID_VISIT_STATE", "Start checkout before completing billing.", 409)
        summary = reconciliation(visit_id)
        if summary["outstanding_units"] or summary["open_service_requests"]:
            raise DomainError("VISIT_NOT_READY", "Serve or cancel every unit and resolve requests first.", 409,
                              {"outstanding_units": summary["outstanding_units"],
                               "open_service_requests": summary["open_service_requests"]})
        closure = one(
            """INSERT INTO closure_record(tenant_id, outlet_id, visit_id, external_bill_ref,
                                          external_total_paise, payment_method_label,
                                          payment_confirmed_by_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            [target["tenant_id"], target["outlet_id"], visit_id,
             billing["external_bill_ref"], billing["external_total_paise"],
             billing["payment_method_label"], actor_id],
        )
        execute("UPDATE dining_visit SET status = 'CLOSED', closed_at = now(), revision = revision + 1 WHERE id = %s", [visit_id])
        execute("UPDATE dining_table SET next_visit_number = next_visit_number + 1, updated_at = now() WHERE id = %s", [table["id"]])
        execute("""UPDATE browser_access SET revoked_at = now()
                   WHERE table_id = %s AND expected_visit_number = %s AND revoked_at IS NULL""",
                [table["id"], visit["visit_number"]])
        audit(target["tenant_id"], target["outlet_id"], actor_id, "visit.closed", "dining_visit", visit_id,
              after={"external_bill_ref": billing["external_bill_ref"], "external_total_paise": billing["external_total_paise"]})
        append_event(target["tenant_id"], target["outlet_id"], "visit.closed", {"visit_id": str(visit_id)}, visit_id)
        return closure, True


def resolve_request(request_id, actor_id):
    with transaction.atomic():
        request = one("SELECT * FROM service_request WHERE id = %s FOR UPDATE", [request_id])
        if not request:
            raise DomainError("REQUEST_NOT_FOUND", "Service request not found.", 404)
        if request["status"] == "OPEN":
            execute("UPDATE service_request SET status = 'RESOLVED', resolved_at = now(), resolved_by_id = %s WHERE id = %s",
                    [actor_id, request_id])
            audit(request["tenant_id"], request["outlet_id"], actor_id, "service_request.resolved", "service_request", request_id)
            append_event(request["tenant_id"], request["outlet_id"], "service_request.resolved",
                         {"request_id": str(request_id)}, request["visit_id"])
        return {"id": request_id, "status": "RESOLVED"}
