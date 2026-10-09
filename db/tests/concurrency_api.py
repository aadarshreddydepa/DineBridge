"""Run only against a disposable *_concurrency_test database."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dinebridge.settings")

import django

django.setup()

from django.conf import settings
from django.db import connections

from api import services, staff
from api.db import all_rows, execute, one


def run():
    if not settings.DATABASES["default"]["NAME"].endswith("_concurrency_test"):
        raise RuntimeError("Use a disposable database ending in _concurrency_test")
    tenant = one("INSERT INTO tenant(slug, legal_name) VALUES ('race', 'Race Test') RETURNING id")
    brand = one("INSERT INTO brand(tenant_id, slug, display_name) VALUES (%s, 'race', 'Race') RETURNING id", [tenant["id"]])
    outlet = one("""INSERT INTO outlet(tenant_id, brand_id, slug, name, ordering_enabled)
                    VALUES (%s, %s, 'one', 'Race One', true) RETURNING id""", [tenant["id"], brand["id"]])
    category = one("INSERT INTO menu_category(tenant_id, brand_id, name) VALUES (%s, %s, 'Mains') RETURNING id",
                   [tenant["id"], brand["id"]])
    item = one("""INSERT INTO menu_item(tenant_id, brand_id, category_id, name)
                  VALUES (%s, %s, %s, 'Dish') RETURNING id""", [tenant["id"], brand["id"], category["id"]])
    variant = one("INSERT INTO item_variant(tenant_id, brand_id, item_id, name) VALUES (%s, %s, %s, 'Regular') RETURNING id",
                  [tenant["id"], brand["id"], item["id"]])
    offering = one("""INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id, price_paise)
                      VALUES (%s, %s, %s, %s, 10000) RETURNING id""",
                   [tenant["id"], brand["id"], outlet["id"], variant["id"]])
    table = one("""INSERT INTO dining_table(tenant_id, outlet_id, label, qr_token_hash)
                   VALUES (%s, %s, 'T1', decode(repeat('aa', 32), 'hex')) RETURNING id""",
                [tenant["id"], outlet["id"]])
    for index in (1, 2):
        execute("""INSERT INTO browser_access(tenant_id, outlet_id, table_id, expected_visit_number,
                                              token_hash, expires_at)
                   VALUES (%s, %s, %s, 1, decode(repeat(%s, 32), 'hex'), now() + interval '12 hours')""",
                [tenant["id"], outlet["id"], table["id"], f"{index:02x}"])
    accesses = all_rows("""SELECT id, tenant_id, outlet_id, table_id, visit_id, expected_visit_number,
                                expires_at, revoked_at FROM browser_access WHERE table_id = %s ORDER BY id""",
                        [table["id"]])
    payload = {"lines": [{"offering_id": offering["id"], "quantity": 1,
                           "expected_version": 1, "expected_price_paise": 10000,
                           "option_ids": [], "notes": ""}]}
    barrier = Barrier(2)

    def submit(index):
        try:
            barrier.wait()
            return services.place_order(accesses[index], payload, f"race-order-{index}")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, (0, 1)))
    assert all(created for _, created in results)
    visits = all_rows("SELECT id FROM dining_visit WHERE table_id = %s", [table["id"]])
    assert len(visits) == 1, visits
    visit_id = visits[0]["id"]
    assert one("SELECT count(*) AS n FROM orders WHERE visit_id = %s", [visit_id])["n"] == 2
    actor = one("INSERT INTO staff_user(email, password) VALUES ('race@example.invalid', '!unusable') RETURNING id")
    staff.start_checkout(visit_id, actor["id"])
    for line in all_rows("SELECT ol.id FROM order_line ol JOIN orders o ON o.id = ol.order_id WHERE o.visit_id = %s", [visit_id]):
        for revision, state in enumerate(("PREPARING", "READY", "SERVED"), start=1):
            staff.progress_line(line["id"], actor["id"], state, 1, revision, "")
    closure, created = staff.complete_billing(visit_id, actor["id"],
                                               {"external_bill_ref": "RACE-1", "external_total_paise": 20000,
                                                "payment_method_label": "cash"})
    repeated, created_again = staff.complete_billing(visit_id, actor["id"],
                                                       {"external_bill_ref": "RACE-1", "external_total_paise": 20000,
                                                        "payment_method_label": "cash"})
    assert created and not created_again and closure["id"] == repeated["id"]
    assert one("SELECT next_visit_number FROM dining_table WHERE id = %s", [table["id"]])["next_visit_number"] == 2
    print("Concurrent first orders shared one visit; closure incremented once")


if __name__ == "__main__":
    run()
