"""Rollback-only end-to-end API smoke test against the local PostgreSQL service."""

import hashlib
import io
import json
import os
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch as mock_patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dinebridge.settings")

import django

django.setup()

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test.utils import override_settings
from PIL import Image

from api.db import execute, one


def post(client, path, body, csrf, **headers):
    return client.post(path, data=json.dumps(body), content_type="application/json",
                       HTTP_X_CSRFTOKEN=csrf, **headers)


def patch(client, path, body, csrf):
    return client.patch(path, data=json.dumps(body), content_type="application/json",
                        HTTP_X_CSRFTOKEN=csrf)


def run():
    with transaction.atomic():
        tenant = one("INSERT INTO tenant(slug, legal_name) VALUES ('api-smoke', 'API Smoke') RETURNING id")
        brand = one("INSERT INTO brand(tenant_id, slug, display_name) VALUES (%s, 'smoke', 'Smoke Kitchen') RETURNING id", [tenant["id"]])
        outlet = one("""INSERT INTO outlet(tenant_id, brand_id, slug, name, ordering_enabled)
                        VALUES (%s, %s, 'one', 'One', true) RETURNING id""", [tenant["id"], brand["id"]])
        category = one("INSERT INTO menu_category(tenant_id, brand_id, name) VALUES (%s, %s, 'Mains') RETURNING id",
                       [tenant["id"], brand["id"]])
        item = one("""INSERT INTO menu_item(tenant_id, brand_id, category_id, name)
                      VALUES (%s, %s, %s, 'Biryani') RETURNING id""", [tenant["id"], brand["id"], category["id"]])
        variant = one("""INSERT INTO item_variant(tenant_id, brand_id, item_id, name)
                         VALUES (%s, %s, %s, 'Regular') RETURNING id""", [tenant["id"], brand["id"], item["id"]])
        offering = one("""INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id,
                                                      price_paise, estimate_max_minutes)
                           VALUES (%s, %s, %s, %s, 29900, 30) RETURNING id""",
                       [tenant["id"], brand["id"], outlet["id"], variant["id"]])
        qr_raw = "smoke-qr-token-with-enough-entropy-for-test"
        table = one("""INSERT INTO dining_table(tenant_id, outlet_id, label, qr_token_hash)
                        VALUES (%s, %s, 'T1', %s) RETURNING id""",
                    [tenant["id"], outlet["id"], hashlib.sha256(qr_raw.encode()).digest()])
        user = one("""INSERT INTO staff_user(email, password, full_name)
                       VALUES ('smoke@example.invalid', %s, 'Smoke Manager') RETURNING id""",
                   [make_password("smoke-password")])
        execute("""INSERT INTO staff_membership(user_id, tenant_id, outlet_id, role)
                   VALUES (%s, %s, %s, 'MANAGER')""", [user["id"], tenant["id"], outlet["id"]])
        execute("""INSERT INTO staff_membership(user_id, tenant_id, role)
                   VALUES (%s, %s, 'OWNER')""", [user["id"], tenant["id"]])

        client = Client(enforce_csrf_checks=True, SERVER_NAME="localhost")
        assert client.get("/healthz").status_code == 200
        config = client.get(f"/api/v1/outlets/{outlet['id']}/config")
        assert config.status_code == 200 and config.json()["display_name"] == "Smoke Kitchen", config.content
        menu = client.get(f"/api/v1/outlets/{outlet['id']}/menu")
        assert menu.status_code == 200 and len(menu.json()["categories"]) == 1, menu.content
        csrf = client.get("/api/v1/csrf").json()["csrf_token"]
        qr = client.get(f"/q/{qr_raw}")
        assert qr.status_code == 302 and "db_access" in qr.cookies, qr.content
        access = client.get("/api/v1/access")
        assert access.status_code == 200 and access.json()["table_label"] == "T1", access.content
        assert str(access.json()["outlet_id"]) == str(outlet["id"]), access.content
        assert one("SELECT count(*) AS n FROM dining_visit WHERE table_id = %s", [table["id"]])["n"] == 0

        order_body = {"lines": [{"offering_id": str(offering["id"]), "quantity": 2,
                                 "expected_version": 1, "expected_price_paise": 29900,
                                 "option_ids": [], "notes": "Mild"}]}
        csrf_fail = client.post("/api/v1/orders", data=json.dumps(order_body), content_type="application/json",
                                HTTP_IDEMPOTENCY_KEY="smoke-order-one")
        assert csrf_fail.status_code == 403, csrf_fail.content
        order_response = post(client, "/api/v1/orders", order_body, csrf, HTTP_IDEMPOTENCY_KEY="smoke-order-one")
        assert order_response.status_code == 201, order_response.content
        order = order_response.json()
        assert order["subtotal_paise"] == 59800
        own_orders = client.get("/api/v1/orders")
        assert own_orders.status_code == 200 and len(own_orders.json()["orders"]) == 1
        retry = post(client, "/api/v1/orders", order_body, csrf, HTTP_IDEMPOTENCY_KEY="smoke-order-one")
        assert retry.status_code == 200 and retry.json()["id"] == order["id"], retry.content
        changed_payload = {"lines": [{**order_body["lines"][0], "quantity": 1}]}
        conflict = post(client, "/api/v1/orders", changed_payload, csrf, HTTP_IDEMPOTENCY_KEY="smoke-order-one")
        assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT", conflict.content
        visit_id = order["visit_id"]
        line_id = order["lines"][0]["id"]

        login = post(client, "/api/v1/staff/login",
                     {"email": "smoke@example.invalid", "password": "smoke-password"}, csrf)
        assert login.status_code == 200 and "db_staff" in login.cookies, login.content
        staff_outlets = client.get("/api/v1/staff/outlets")
        assert staff_outlets.status_code == 200 and len(staff_outlets.json()["outlets"]) == 1, staff_outlets.content
        assert staff_outlets.json()["outlets"][0]["can_edit_brand"] is True
        staff_catalogue = client.get(f"/api/v1/staff/outlets/{outlet['id']}/catalogue")
        assert staff_catalogue.status_code == 200 and len(staff_catalogue.json()["items"]) == 1, staff_catalogue.content
        quick_item = post(client, f"/api/v1/staff/outlets/{outlet['id']}/quick-items",
                          {"category_id": str(category["id"]), "name": "Fresh Lime Soda",
                           "dietary_type": "VEGAN", "price_paise": 9900,
                           "estimate_max_minutes": 10}, csrf)
        assert quick_item.status_code == 201, quick_item.content
        assert one("SELECT count(*) AS n FROM outlet_offering WHERE outlet_id = %s", [outlet["id"]])["n"] == 2
        public_menu = client.get(f"/api/v1/outlets/{outlet['id']}/menu").json()
        assert any(dish["name"] == "Fresh Lime Soda" for section in public_menu["categories"] for dish in section["items"])
        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=Path(media_dir)):
            image_buffer = io.BytesIO()
            Image.new("RGB", (24, 24), "#61a98c").save(image_buffer, format="PNG")
            image_bytes = image_buffer.getvalue()
            image_path = f"/api/v1/staff/items/{quick_item.json()['item']['id']}/images"
            uploaded = client.post(image_path, {
                "images": [SimpleUploadedFile("front.png", image_bytes, content_type="image/png"),
                           SimpleUploadedFile("side.png", image_bytes, content_type="image/png")]
            }, HTTP_X_CSRFTOKEN=csrf)
            assert uploaded.status_code == 201 and len(uploaded.json()["images"]) == 2, uploaded.content
            public_menu = client.get(f"/api/v1/outlets/{outlet['id']}/menu").json()
            quick_dish = next(dish for section in public_menu["categories"] for dish in section["items"]
                              if dish["name"] == "Fresh Lime Soda")
            assert len(quick_dish["image_urls"]) == 2 and quick_dish["image_url"].startswith("/uploads/")
            removed = client.delete(f"{image_path}/{uploaded.json()['images'][0]['id']}", HTTP_X_CSRFTOKEN=csrf)
            assert removed.status_code == 200 and len(removed.json()["images"]) == 1, removed.content
        with override_settings(OPENAI_API_KEY=""):
            no_ai = post(client, f"/api/v1/staff/outlets/{outlet['id']}/description-draft",
                         {"title": "Fresh Lime Soda", "draft": "Lime and soda"}, csrf)
            assert no_ai.status_code == 503 and no_ai.json()["code"] == "AI_NOT_CONFIGURED", no_ai.content
        fake_ai = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Fresh lime soda with a bright citrus finish."}]}]}
        with override_settings(OPENAI_API_KEY="test"), mock_patch("api.ai_views.urlopen", return_value=io.BytesIO(json.dumps(fake_ai).encode())):
            drafted = post(client, f"/api/v1/staff/outlets/{outlet['id']}/description-draft",
                           {"title": "Fresh Lime Soda", "draft": "Lime and soda"}, csrf)
            assert drafted.status_code == 200 and drafted.json()["description"].startswith("Fresh lime"), drafted.content
        new_table = post(client, f"/api/v1/staff/outlets/{outlet['id']}/tables", {"label": "T2"}, csrf)
        assert new_table.status_code == 201 and "/q/" in new_table.json()["qr_url"], new_table.content
        group = post(client, f"/api/v1/staff/variants/{variant['id']}/modifier-groups",
                     {"name": "Extras", "min_choices": 0, "max_choices": 1}, csrf)
        assert group.status_code == 201, group.content
        option = post(client, f"/api/v1/staff/modifier-groups/{group.json()['id']}/options",
                      {"name": "Raita"}, csrf)
        assert option.status_code == 201, option.content
        outlet_modifier = post(client, f"/api/v1/staff/outlets/{outlet['id']}/modifiers",
                               {"option_id": option.json()["id"], "price_delta_paise": 2500}, csrf)
        assert outlet_modifier.status_code == 201, outlet_modifier.content
        refreshed_menu = client.get(f"/api/v1/outlets/{outlet['id']}/menu").json()
        assert refreshed_menu["categories"][0]["items"][0]["variants"][0]["modifier_groups"][0]["options"][0]["name"] == "Raita"
        brand_update = patch(client, f"/api/v1/staff/brands/{brand['id']}",
                             {"display_name": "Smoke Kitchen Updated"}, csrf)
        assert brand_update.status_code == 200, brand_update.content
        override = patch(client, f"/api/v1/staff/outlets/{outlet['id']}/branding",
                         {"display_name": "Smoke at One"}, csrf)
        assert override.status_code == 200, override.content
        assert client.get(f"/api/v1/outlets/{outlet['id']}/config").json()["display_name"] == "Smoke at One"
        tables = client.get(f"/api/v1/staff/outlets/{outlet['id']}/tables")
        assert tables.status_code == 200 and sum(t["unseen_orders"] for t in tables.json()["tables"]) == 1, tables.content
        queue = client.get(f"/api/v1/staff/outlets/{outlet['id']}/queue")
        assert queue.status_code == 200 and len(queue.json()["lines"]) == 1, queue.content
        visit_orders = client.get(f"/api/v1/staff/visits/{visit_id}/orders")
        assert visit_orders.status_code == 200 and len(visit_orders.json()["orders"]) == 1, visit_orders.content
        stream = client.get(f"/api/v1/staff/outlets/{outlet['id']}/events/stream")
        assert stream.status_code == 200 and stream["Content-Type"].startswith("text/event-stream")
        checkout = post(client, f"/api/v1/staff/visits/{visit_id}/checkout", {}, csrf)
        assert checkout.status_code == 200 and checkout.json()["status"] == "CHECKOUT", checkout.content
        late_order = post(client, "/api/v1/orders", order_body, csrf, HTTP_IDEMPOTENCY_KEY="smoke-order-two")
        assert late_order.status_code == 409 and late_order.json()["code"] == "VISIT_IN_CHECKOUT", late_order.content
        billing_body = {"external_bill_ref": "POS-100", "external_total_paise": 59800,
                        "payment_method_label": "cash"}
        premature = post(client, f"/api/v1/staff/visits/{visit_id}/complete-billing", billing_body, csrf)
        assert premature.status_code == 409 and premature.json()["code"] == "VISIT_NOT_READY", premature.content

        for revision, state in enumerate(("PREPARING", "READY", "SERVED"), start=1):
            changed = patch(client, f"/api/v1/staff/lines/{line_id}/progress",
                            {"to_state": state, "quantity": 2, "expected_revision": revision}, csrf)
            assert changed.status_code == 200 and changed.json()["revision"] == revision + 1, changed.content
        completed = post(client, f"/api/v1/staff/visits/{visit_id}/complete-billing", billing_body, csrf)
        assert completed.status_code == 201, completed.content
        repeated = post(client, f"/api/v1/staff/visits/{visit_id}/complete-billing", billing_body, csrf)
        assert repeated.status_code == 200 and repeated.json()["id"] == completed.json()["id"], repeated.content
        assert one("SELECT next_visit_number FROM dining_table WHERE id = %s", [table["id"]])["next_visit_number"] == 2
        assert one("SELECT revoked_at FROM browser_access WHERE visit_id = %s", [visit_id])["revoked_at"] is not None
        events = client.get(f"/api/v1/staff/outlets/{outlet['id']}/events")
        assert events.status_code == 200 and len(events.json()["events"]) >= 5, events.content
        price_edit = patch(client, f"/api/v1/staff/outlets/{outlet['id']}/offerings/{offering['id']}",
                           {"expected_version": 1, "price_paise": 32900}, csrf)
        assert price_edit.status_code == 200 and price_edit.json()["version"] == 2, price_edit.content
        assert client.get(f"/q/{qr_raw}").status_code == 302
        stale_price = post(client, "/api/v1/orders", order_body, csrf, HTTP_IDEMPOTENCY_KEY="smoke-order-three")
        assert stale_price.status_code == 409 and stale_price.json()["code"] == "PRICE_CHANGED", stale_price.content
        rotated = post(client, f"/api/v1/staff/tables/{table['id']}/rotate-qr", {}, csrf)
        assert rotated.status_code == 200 and "/q/" in rotated.json()["qr_url"], rotated.content
        assert client.get(f"/q/{qr_raw}").status_code == 404

        transaction.set_rollback(True)
    stream.close()
    print("API smoke flow passed; sample records rolled back")


if __name__ == "__main__":
    run()
