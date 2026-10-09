import hashlib
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from api.db import one
from api.errors import DomainError


STAFF_COOKIE = "db_staff"
ACCESS_COOKIE = "db_access"
STAFF_MAX_AGE = 12 * 60 * 60
ACCESS_MAX_AGE = 12 * 60 * 60


def cookie_options(max_age):
    return {
        "max_age": max_age,
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": settings.CSRF_COOKIE_SAMESITE,
        "path": "/",
    }


def staff_from_request(request):
    signed = request.COOKIES.get(STAFF_COOKIE)
    if not signed:
        raise DomainError("AUTH_REQUIRED", "Staff login required.", 401)
    try:
        data = signing.loads(signed, salt="dinebridge.staff", max_age=STAFF_MAX_AGE)
    except signing.BadSignature as exc:
        raise DomainError("AUTH_REQUIRED", "Staff session expired or invalid.", 401) from exc
    user = one("SELECT id, email, full_name FROM staff_user WHERE id = %s AND is_active", [data["uid"]])
    if not user:
        raise DomainError("AUTH_REQUIRED", "Staff account is inactive.", 401)
    return user


def require_outlet_role(request, outlet_id, roles):
    user = staff_from_request(request)
    membership = one(
        """SELECT sm.role, sm.tenant_id FROM staff_membership sm
           JOIN outlet o ON o.id = %s AND o.tenant_id = sm.tenant_id
           WHERE sm.user_id = %s AND sm.active
             AND (sm.outlet_id = o.id OR sm.outlet_id IS NULL)
             AND sm.role = ANY(%s)
           ORDER BY (sm.outlet_id IS NOT NULL) DESC LIMIT 1""",
        [outlet_id, user["id"], list(roles)],
    )
    if not membership:
        raise DomainError("FORBIDDEN", "No permitted role for this outlet.", 403)
    return user, membership


def require_tenant_role(request, tenant_id, roles):
    user = staff_from_request(request)
    membership = one(
        """SELECT role FROM staff_membership
           WHERE user_id = %s AND tenant_id = %s AND outlet_id IS NULL
             AND active AND role = ANY(%s) LIMIT 1""",
        [user["id"], tenant_id, list(roles)],
    )
    if not membership:
        raise DomainError("FORBIDDEN", "A tenant owner or manager role is required.", 403)
    return user


def access_from_request(request, *, allow_revoked=False):
    raw = request.COOKIES.get(ACCESS_COOKIE)
    if not raw:
        raise DomainError("ACCESS_REQUIRED", "Scan the table QR code first.", 401)
    try:
        token_hash = hashlib.sha256(raw.encode("ascii")).digest()
    except UnicodeEncodeError as exc:
        raise DomainError("ACCESS_EXPIRED", "Scan the table QR code again.", 401) from exc
    access = one(
        """SELECT id, tenant_id, outlet_id, table_id, visit_id, expected_visit_number,
                  expires_at, revoked_at
           FROM browser_access WHERE token_hash = %s""",
        [token_hash],
    )
    if not access or access["expires_at"] <= timezone.now() or (access["revoked_at"] and not allow_revoked):
        raise DomainError("ACCESS_EXPIRED", "Scan the table QR code again.", 401)
    return access


def access_expiry():
    return timezone.now() + timedelta(seconds=ACCESS_MAX_AGE)
