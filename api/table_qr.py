"""Derive a stable, unguessable table QR token from the app secret and a stored nonce."""

import base64
import hashlib
import hmac

from django.conf import settings


def table_qr_token(table_id, nonce):
    message = b"dinebridge-table-qr-v1:" + table_id.bytes + bytes(nonce)
    digest = hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def table_qr_url(request, raw):
    base = settings.QR_PUBLIC_BASE_URL or request.build_absolute_uri("/").rstrip("/")
    return f"{base}/q/{raw}"
