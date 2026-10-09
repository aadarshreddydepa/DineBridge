"""Create disposable local data for the full customer and staff flow."""

import hashlib
import json
import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from psycopg.types.json import Jsonb

from api.db import execute, one


DISHES = [
    ("Signatures", "The Greenhouse Bowl", "Roasted greens, avocado, herbed quinoa and lemon tahini.", "VEGAN", 44900, 25, "photo-1512621776951-a57141f2eefd"),
    ("Signatures", "Wild Mushroom Pizza", "Forest mushrooms, ricotta, mozzarella and truffle oil.", "VEGETARIAN", 59500, 30, "photo-1574071318508-1cdbab80d002"),
    ("Signatures", "Fire-Roasted Chicken", "Slow-roasted chicken, whipped potatoes and charred greens.", "NON_VEGETARIAN", 68500, 35, "photo-1532550907401-a500c9a57435"),
    ("Small Plates", "Silky Hummus & Pita", "Warm pita, chickpea hummus, chilli oil and sesame.", "VEGAN", 28500, 20, "photo-1577906096429-f73c2c312435"),
    ("Small Plates", "Heirloom Tomato Salad", "Ripe tomatoes, basil, creamy burrata and aged balsamic.", "VEGETARIAN", 34500, 20, "photo-1547592180-85f173990554"),
    ("Drinks", "Garden Lemonade", "Fresh lemon, basil, soda and lots of ice.", "VEGAN", 17500, 15, "photo-1546173159-315724a31696"),
]


class Command(BaseCommand):
    help = "Seed a disposable local restaurant, owner, menu and QR tables (DEBUG only)"

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Local demo seeding is disabled when DJANGO_DEBUG=0.")
        if one("SELECT id FROM tenant WHERE slug = 'olive-ember-demo'"):
            raise CommandError("The local demo already exists; its QR tokens cannot be recovered. Rotate them in the staff portal.")
        password = secrets.token_urlsafe(18)
        owner_email = "demo-owner@local.invalid"
        if one("SELECT id FROM staff_user WHERE lower(email) = %s", [owner_email]):
            raise CommandError("The demo owner email already exists.")
        with transaction.atomic():
            tenant = one("INSERT INTO tenant(slug, legal_name) VALUES ('olive-ember-demo', 'Olive & Ember Demo') RETURNING id")
            brand = one(
                """INSERT INTO brand(tenant_id, slug, display_name, primary_color, accent_color, presentation)
                   VALUES (%s, 'olive-ember', 'Olive & Ember', '#263b32', '#d97a55', %s) RETURNING id""",
                [tenant["id"], Jsonb({"tagline": "EAT WELL. FEEL GOOD.", "hero_headline": "Stay a while.", "hero_emphasis": "Eat beautifully."})],
            )
            outlet = one(
                """INSERT INTO outlet(tenant_id, brand_id, slug, name, ordering_enabled)
                   VALUES (%s, %s, 'main', 'Main Restaurant', true) RETURNING id""",
                [tenant["id"], brand["id"]],
            )
            user = one(
                "INSERT INTO staff_user(email, password, full_name) VALUES (%s, %s, 'Demo Owner') RETURNING id",
                [owner_email, make_password(password)],
            )
            execute("INSERT INTO staff_membership(user_id, tenant_id, role) VALUES (%s, %s, 'OWNER')", [user["id"], tenant["id"]])
            categories = {}
            for number, name in enumerate(("Signatures", "Small Plates", "Drinks")):
                categories[name] = one(
                    "INSERT INTO menu_category(tenant_id, brand_id, name, display_order) VALUES (%s, %s, %s, %s) RETURNING id",
                    [tenant["id"], brand["id"], name, number],
                )["id"]
            for category, name, description, diet, price, estimate, image_key in DISHES:
                asset = one(
                    """INSERT INTO media_asset(tenant_id, storage_key, mime_type, size_bytes, status, alt_text)
                       VALUES (%s, %s, 'image/jpeg', 1, 'READY', %s) RETURNING id""",
                    [tenant["id"], image_key, name],
                )
                item = one(
                    """INSERT INTO menu_item(tenant_id, brand_id, category_id, name, description, dietary_type, image_asset_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    [tenant["id"], brand["id"], categories[category], name, description, diet, asset["id"]],
                )
                variant = one(
                    "INSERT INTO item_variant(tenant_id, brand_id, item_id, name) VALUES (%s, %s, %s, 'Regular') RETURNING id",
                    [tenant["id"], brand["id"], item["id"]],
                )
                execute(
                    """INSERT INTO outlet_offering(tenant_id, brand_id, outlet_id, variant_id, price_paise, estimate_max_minutes)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    [tenant["id"], brand["id"], outlet["id"], variant["id"], price, estimate],
                )
            qr_base = settings.QR_PUBLIC_BASE_URL or "http://127.0.0.1:8000"
            qr_urls = {}
            for label in ("Table 01", "Table 02", "Table 03"):
                raw = secrets.token_urlsafe(32)
                execute(
                    "INSERT INTO dining_table(tenant_id, outlet_id, label, qr_token_hash) VALUES (%s, %s, %s, %s)",
                    [tenant["id"], outlet["id"], label, hashlib.sha256(raw.encode()).digest()],
                )
                qr_urls[label] = f"{qr_base}/q/{raw}"
        return json.dumps({"staff_url": "http://127.0.0.1:5173/staff", "owner_email": owner_email,
                           "owner_password": password, "outlet_id": str(outlet["id"]), "table_qr_urls": qr_urls}, indent=2)
