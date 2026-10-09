"""Create the first client, brand, outlet and owner without exposing a public setup API."""

from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.db import execute, one


class Command(BaseCommand):
    help = "Create a tenant, brand, outlet and tenant owner"

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True)
        parser.add_argument("--legal-name", required=True)
        parser.add_argument("--brand-slug", required=True)
        parser.add_argument("--brand-name", required=True)
        parser.add_argument("--outlet-slug", required=True)
        parser.add_argument("--outlet-name", required=True)
        parser.add_argument("--owner-email", required=True)

    def handle(self, *args, **options):
        password = getpass("Owner password: ")
        confirm = getpass("Confirm password: ")
        if len(password) < 12 or password != confirm:
            raise CommandError("Passwords must match and contain at least 12 characters.")
        email = options["owner_email"].strip().lower()
        if one("SELECT id FROM staff_user WHERE lower(email) = %s", [email]):
            raise CommandError("Owner email already exists.")
        with transaction.atomic():
            tenant = one("INSERT INTO tenant(slug, legal_name) VALUES (%s, %s) RETURNING id",
                         [options["tenant_slug"], options["legal_name"]])
            brand = one("""INSERT INTO brand(tenant_id, slug, display_name)
                           VALUES (%s, %s, %s) RETURNING id""",
                        [tenant["id"], options["brand_slug"], options["brand_name"]])
            outlet = one("""INSERT INTO outlet(tenant_id, brand_id, slug, name)
                            VALUES (%s, %s, %s, %s) RETURNING id""",
                         [tenant["id"], brand["id"], options["outlet_slug"], options["outlet_name"]])
            user = one("INSERT INTO staff_user(email, password) VALUES (%s, %s) RETURNING id",
                       [email, make_password(password)])
            execute("""INSERT INTO staff_membership(user_id, tenant_id, role)
                       VALUES (%s, %s, 'OWNER')""", [user["id"], tenant["id"]])
        self.stdout.write(self.style.SUCCESS(
            f"Created tenant {tenant['id']}, brand {brand['id']}, outlet {outlet['id']}, owner {email}."
        ))
