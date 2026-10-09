"""Tenant-scoped menu photos stored on the configured media volume."""

import io
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.admin_views import _brand_event
from api.auth import require_tenant_role
from api.catalog import _asset_url
from api.csrf import require_csrf
from api.db import all_rows, one
from api.errors import DomainError


register_heif_opener(thumbnails=False)

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_IMAGES_PER_ITEM = 10


def _item(item_id):
    item = one("SELECT id, tenant_id, brand_id, name FROM menu_item WHERE id = %s AND active", [item_id])
    if not item:
        raise DomainError("ITEM_NOT_FOUND", "Menu item not found.", 404)
    return item


def _images(item_id):
    rows = all_rows(
        """SELECT mii.id, mii.display_order, ma.alt_text, ma.storage_key
           FROM menu_item_image mii JOIN media_asset ma ON ma.id = mii.asset_id
           WHERE mii.item_id = %s AND mii.active AND ma.status = 'READY'
           ORDER BY mii.display_order, mii.id""",
        [item_id],
    )
    for row in rows:
        row["url"] = _asset_url(row.pop("storage_key"))
    return rows


def _prepare(upload):
    raw = upload.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise DomainError("IMAGE_TOO_LARGE", "Each photo must be 12 MB or less.", 422)
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP", "HEIF"}:
                raise DomainError("INVALID_IMAGE", "Upload a JPEG, PNG, WebP, or HEIC photo.", 422)
            if source.width * source.height > MAX_PIXELS:
                raise DomainError("IMAGE_TOO_LARGE", "Photo resolution is too large. Choose a smaller image.", 422)
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=82, method=6)
            return output.getvalue(), image.width, image.height
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise DomainError("INVALID_IMAGE", "Upload a valid JPEG, PNG, WebP, or HEIC photo.", 422)


@api_view(["GET", "POST"])
@require_csrf
def item_images(request, item_id):
    item = _item(item_id)
    user = require_tenant_role(request, item["tenant_id"], {"OWNER", "MANAGER"})
    if request.method == "GET":
        return Response({"images": _images(item_id)})

    uploads = request.FILES.getlist("images")
    if not uploads or len(uploads) > MAX_IMAGES_PER_ITEM:
        raise DomainError("INVALID_IMAGES", "Select up to 10 photos.", 422)
    prepared = [_prepare(upload) for upload in uploads]
    created_paths: list[Path] = []
    committed = False
    try:
        with transaction.atomic():
            one("SELECT id FROM menu_item WHERE id = %s FOR UPDATE", [item_id])
            count = one("SELECT count(*) AS n, coalesce(max(display_order), -1) AS last_order "
                        "FROM menu_item_image WHERE item_id = %s AND active", [item_id])
            if count["n"] + len(prepared) > MAX_IMAGES_PER_ITEM:
                raise DomainError("IMAGE_LIMIT", "A dish can have up to 10 photos.", 422)
            for offset, (content, width, height) in enumerate(prepared, start=1):
                key = f"uploaded/{item['tenant_id']}/{uuid.uuid4().hex}.webp"
                path = settings.MEDIA_ROOT / key
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as file:
                        file.write(content)
                except OSError:
                    raise DomainError("PHOTO_STORAGE_UNAVAILABLE", "Photo storage is unavailable. Try again shortly.", 503)
                created_paths.append(path)
                asset = one(
                    """INSERT INTO media_asset(tenant_id, storage_key, mime_type, width_px, height_px,
                                               size_bytes, alt_text, status)
                       VALUES (%s, %s, 'image/webp', %s, %s, %s, %s, 'READY') RETURNING id""",
                    [item["tenant_id"], key, width, height, len(content), item["name"]],
                )
                one(
                    """INSERT INTO menu_item_image(tenant_id, brand_id, item_id, asset_id, display_order)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    [item["tenant_id"], item["brand_id"], item_id, asset["id"], count["last_order"] + offset],
                )
            _brand_event({"id": item["brand_id"], "tenant_id": item["tenant_id"]}, user["id"],
                         "catalogue.images_added", "menu_item", item_id)
        committed = True
    finally:
        if not committed:
            for path in created_paths:
                path.unlink(missing_ok=True)
    return Response({"images": _images(item_id)}, status=201)


@api_view(["DELETE"])
@require_csrf
def item_image_remove(request, item_id, image_id):
    item = _item(item_id)
    user = require_tenant_role(request, item["tenant_id"], {"OWNER", "MANAGER"})
    with transaction.atomic():
        target = one("SELECT id FROM menu_item_image WHERE id = %s AND item_id = %s AND active FOR UPDATE",
                     [image_id, item_id])
        if not target:
            raise DomainError("IMAGE_NOT_FOUND", "Photo not found.", 404)
        one("UPDATE menu_item_image SET active = false WHERE id = %s RETURNING id", [image_id])
        _brand_event({"id": item["brand_id"], "tenant_id": item["tenant_id"]}, user["id"],
                     "catalogue.image_removed", "menu_item", item_id)
    return Response({"images": _images(item_id)})
