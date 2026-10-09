import asyncio
import json
from urllib.parse import urlencode

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import signing
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api import admin_views, catalog, services, staff
from api.auth import (ACCESS_COOKIE, ACCESS_MAX_AGE, STAFF_COOKIE, STAFF_MAX_AGE,
                      access_from_request, cookie_options, require_outlet_role,
                      staff_from_request)
from api.db import all_rows, execute, one
from api.csrf import require_csrf
from api.errors import DomainError
from api.serializers import (BillingInput, OrderInput, ProgressInput,
                             ServiceRequestInput, StaffLoginInput)
from django.db import transaction


@api_view(["GET"])
def health(request):
    one("SELECT 1 AS ok")
    return Response({"status": "ok"})


@ensure_csrf_cookie
@api_view(["GET"])
def csrf_cookie(request):
    return Response({"csrf_token": get_token(request)})


@api_view(["GET"])
def outlet_config(request, outlet_id):
    return Response(catalog.outlet_config(outlet_id))


@api_view(["GET"])
def outlet_menu(request, outlet_id):
    return Response(catalog.outlet_menu(outlet_id))


@never_cache
@api_view(["GET"])
def qr_bootstrap(request, token):
    raw, access = services.bootstrap_access(token)
    url = f"{settings.FRONTEND_URL}/menu?{urlencode({'outlet': str(access['outlet_id'])})}"
    response = HttpResponseRedirect(url)
    response.set_cookie(ACCESS_COOKIE, raw, **cookie_options(ACCESS_MAX_AGE))
    response["Referrer-Policy"] = "no-referrer"
    response["Cache-Control"] = "no-store"
    return response


@api_view(["GET", "POST"])
@require_csrf
def orders(request):
    access = access_from_request(request, allow_revoked=request.method == "POST")
    if request.method == "GET":
        owned = all_rows("SELECT id FROM orders WHERE browser_access_id = %s ORDER BY placed_at, id", [access["id"]])
        return Response({"orders": [services.order_snapshot(row["id"]) for row in owned]})
    serializer = OrderInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    order_id, created = services.place_order(access, serializer.validated_data,
                                              request.headers.get("Idempotency-Key", ""))
    return Response(services.order_snapshot(order_id), status=201 if created else 200)


@api_view(["GET"])
def order_detail(request, order_id):
    access = access_from_request(request)
    owned = one("SELECT id FROM orders WHERE id = %s AND browser_access_id = %s", [order_id, access["id"]])
    if not owned:
        raise DomainError("ORDER_NOT_FOUND", "Order not found.", 404)
    return Response(services.order_snapshot(order_id))


@api_view(["POST"])
@require_csrf
def service_requests(request):
    access = access_from_request(request)
    serializer = ServiceRequestInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    kind = serializer.validated_data["kind"]
    with transaction.atomic():
        one("SELECT id FROM dining_table WHERE id = %s FOR UPDATE", [access["table_id"]])
        current = one("SELECT * FROM browser_access WHERE id = %s FOR UPDATE", [access["id"]])
        if current["revoked_at"] or not current["visit_id"]:
            raise DomainError("NO_ACTIVE_VISIT", "Place an order before requesting service.", 409)
        visit = one("SELECT status FROM dining_visit WHERE id = %s", [current["visit_id"]])
        if visit["status"] == "CLOSED":
            raise DomainError("VISIT_CLOSED", "Scan the QR code again.", 409)
        existing = one(
            """SELECT id, kind, status, requested_at FROM service_request
               WHERE browser_access_id = %s AND kind = %s AND status = 'OPEN'""",
            [access["id"], kind],
        )
        if existing:
            return Response(existing, status=200)
        saved = one(
            """INSERT INTO service_request(tenant_id, outlet_id, visit_id, browser_access_id, kind)
               VALUES (%s, %s, %s, %s, %s) RETURNING id, kind, status, requested_at""",
            [access["tenant_id"], access["outlet_id"], current["visit_id"], access["id"], kind],
        )
        services.append_event(access["tenant_id"], access["outlet_id"], "service_request.opened",
                              {"request_id": str(saved["id"]), "kind": kind}, current["visit_id"])
        return Response(saved, status=201)


@api_view(["POST"])
@require_csrf
def staff_login(request):
    serializer = StaffLoginInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].strip().lower()
    user = one("SELECT id, email, full_name, password FROM staff_user WHERE lower(email) = %s AND is_active", [email])
    if not user or not check_password(serializer.validated_data["password"], user["password"]):
        raise DomainError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    signed = signing.dumps({"uid": str(user["id"])}, salt="dinebridge.staff", compress=True)
    response = Response({"id": user["id"], "email": user["email"], "full_name": user["full_name"]})
    response.set_cookie(STAFF_COOKIE, signed, **cookie_options(STAFF_MAX_AGE))
    return response


@api_view(["POST"])
@require_csrf
def staff_logout(request):
    response = Response({"status": "logged_out"})
    response.delete_cookie(STAFF_COOKIE, path="/")
    return response


@api_view(["GET"])
def staff_me(request):
    user = staff_from_request(request)
    memberships = all_rows(
        "SELECT tenant_id, outlet_id, role FROM staff_membership WHERE user_id = %s AND active ORDER BY role",
        [user["id"]],
    )
    return Response({**user, "memberships": memberships})


@api_view(["GET", "POST"])
@require_csrf
def staff_tables(request, outlet_id):
    if request.method == "POST":
        return admin_views.create_table(request, outlet_id)
    require_outlet_role(request, outlet_id, {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    return Response(staff.tables_snapshot(outlet_id))


@api_view(["GET"])
def staff_queue(request, outlet_id):
    require_outlet_role(request, outlet_id, {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    return Response({"outlet_id": outlet_id, "lines": staff.kitchen_queue(outlet_id)})


@api_view(["GET"])
def staff_requests(request, outlet_id):
    require_outlet_role(request, outlet_id, {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    rows = all_rows(
        """SELECT sr.id, sr.visit_id, sr.kind, sr.requested_at, dt.label AS table_label
           FROM service_request sr JOIN dining_visit dv ON dv.id = sr.visit_id
           JOIN dining_table dt ON dt.id = dv.table_id
           WHERE sr.outlet_id = %s AND sr.status = 'OPEN' ORDER BY sr.requested_at""",
        [outlet_id],
    )
    return Response({"outlet_id": outlet_id, "requests": rows})


@api_view(["GET"])
def staff_visit_orders(request, visit_id):
    _visit_staff(request, visit_id, {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    orders_for_visit = all_rows("SELECT id FROM orders WHERE visit_id = %s ORDER BY placed_at, id", [visit_id])
    return Response({"visit_id": visit_id,
                     "orders": [services.order_snapshot(row["id"]) for row in orders_for_visit],
                     "reconciliation": staff.reconciliation(visit_id)})


@api_view(["POST"])
@require_csrf
def staff_order_seen(request, order_id):
    order = one("SELECT outlet_id FROM orders WHERE id = %s", [order_id])
    if not order:
        raise DomainError("ORDER_NOT_FOUND", "Order not found.", 404)
    user, _ = require_outlet_role(request, order["outlet_id"], {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    staff.mark_seen(order_id, user["id"])
    return Response({"id": order_id, "seen": True})


@api_view(["PATCH"])
@require_csrf
def staff_line_progress(request, line_id):
    serializer = ProgressInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    target = one("SELECT outlet_id FROM order_line WHERE id = %s", [line_id])
    if not target:
        raise DomainError("LINE_NOT_FOUND", "Order line not found.", 404)
    roles = ({"OWNER", "MANAGER"} if data["to_state"] == "CANCELLED" else
             {"OWNER", "MANAGER", "WAITER"} if data["to_state"] == "SERVED" else
             {"OWNER", "MANAGER", "KITCHEN"})
    user, _ = require_outlet_role(request, target["outlet_id"], roles)
    return Response(staff.progress_line(line_id, user["id"], data["to_state"],
                                        data["quantity"], data["expected_revision"], data["reason"],
                                        data.get("from_state")))


def _visit_staff(request, visit_id, roles):
    visit = one("SELECT outlet_id FROM dining_visit WHERE id = %s", [visit_id])
    if not visit:
        raise DomainError("VISIT_NOT_FOUND", "Visit not found.", 404)
    user, _ = require_outlet_role(request, visit["outlet_id"], roles)
    return user


@api_view(["POST"])
@require_csrf
def staff_checkout(request, visit_id):
    user = _visit_staff(request, visit_id, {"OWNER", "MANAGER", "CASHIER"})
    return Response(staff.start_checkout(visit_id, user["id"]))


@api_view(["POST"])
@require_csrf
def staff_cancel_checkout(request, visit_id):
    user = _visit_staff(request, visit_id, {"OWNER", "MANAGER", "CASHIER"})
    return Response(staff.cancel_checkout(visit_id, user["id"]))


@api_view(["POST"])
@require_csrf
def staff_complete_billing(request, visit_id):
    user = _visit_staff(request, visit_id, {"OWNER", "MANAGER", "CASHIER"})
    serializer = BillingInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    closure, created = staff.complete_billing(visit_id, user["id"], serializer.validated_data)
    return Response(closure, status=201 if created else 200)


@api_view(["POST"])
@require_csrf
def staff_resolve_request(request, request_id):
    target = one("SELECT outlet_id FROM service_request WHERE id = %s", [request_id])
    if not target:
        raise DomainError("REQUEST_NOT_FOUND", "Service request not found.", 404)
    user, _ = require_outlet_role(request, target["outlet_id"], {"OWNER", "MANAGER", "WAITER", "CASHIER"})
    return Response(staff.resolve_request(request_id, user["id"]))


@api_view(["GET"])
def staff_events(request, outlet_id):
    require_outlet_role(request, outlet_id, {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    after = _event_cursor(request)
    if _cursor_expired(outlet_id, after):
        return Response({"resync_required": True}, status=409)
    rows = all_rows(
        """SELECT id, event_type, payload, created_at FROM domain_event
           WHERE outlet_id = %s AND id > %s AND created_at > now() - interval '7 days'
           ORDER BY id LIMIT 200""",
        [outlet_id, after],
    )
    return Response({"outlet_id": outlet_id, "events": rows,
                     "cursor": rows[-1]["id"] if rows else after})


def _event_cursor(request):
    try:
        value = int(request.headers.get("Last-Event-ID") or request.query_params.get("after", "0"))
    except ValueError as exc:
        raise DomainError("INVALID_CURSOR", "Event cursor must be an integer.", 400) from exc
    if value < 0 or value > 2**63 - 1:
        raise DomainError("INVALID_CURSOR", "Event cursor is out of range.", 400)
    return value


def _cursor_expired(outlet_id, after):
    if after == 0:
        return False
    old = one(
        """SELECT max(id) AS id FROM domain_event WHERE outlet_id = %s
           AND created_at <= now() - interval '7 days'""",
        [outlet_id],
    )
    return old["id"] is not None and after <= old["id"]


@api_view(["GET"])
def staff_event_stream(request, outlet_id):
    require_outlet_role(request, outlet_id, {"OWNER", "MANAGER", "CASHIER", "KITCHEN", "WAITER"})
    after = _event_cursor(request)
    if _cursor_expired(outlet_id, after):
        return Response({"resync_required": True}, status=409)

    async def stream():
        cursor = after
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 30
        last_heartbeat = loop.time()
        while loop.time() < deadline:
            rows = await sync_to_async(all_rows, thread_sensitive=True)(
                """SELECT id, event_type, payload, created_at FROM domain_event
                   WHERE outlet_id = %s AND id > %s AND created_at > now() - interval '7 days'
                   ORDER BY id LIMIT 100""",
                [outlet_id, cursor],
            )
            for row in rows:
                cursor = row["id"]
                data = json.dumps(row, cls=DjangoJSONEncoder, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {row['event_type']}\ndata: {data}\n\n"
            if loop.time() - last_heartbeat >= 15:
                yield ": heartbeat\n\n"
                last_heartbeat = loop.time()
            await asyncio.sleep(2)

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response
