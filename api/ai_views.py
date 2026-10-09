"""Optional, staff-only description drafting via the OpenAI Responses API."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.auth import require_tenant_role
from api.csrf import require_csrf
from api.db import one
from api.errors import DomainError


class DescriptionDraftInput(serializers.Serializer):
    title = serializers.CharField(max_length=160)
    draft = serializers.CharField(max_length=800, allow_blank=True, required=False, default="")


def _response_text(payload):
    return "".join(
        content.get("text", "")
        for item in payload.get("output", [])
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") == "output_text"
    ).strip()


@api_view(["POST"])
@require_csrf
def description_draft(request, outlet_id):
    outlet = one("SELECT tenant_id FROM outlet WHERE id = %s AND active", [outlet_id])
    if not outlet:
        raise DomainError("OUTLET_NOT_FOUND", "Outlet not found.", 404)
    require_tenant_role(request, outlet["tenant_id"], {"OWNER", "MANAGER"})
    serializer = DescriptionDraftInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    if not settings.OPENAI_API_KEY:
        raise DomainError("AI_NOT_CONFIGURED", "AI suggestions are not configured for this server.", 503)
    data = serializer.validated_data
    body = {
        "model": settings.OPENAI_MODEL,
        "store": False,
        "reasoning": {"effort": "none"},
        "max_output_tokens": 160,
        "instructions": (
            "Write one polished restaurant-menu description, 15 to 35 words. "
            "Use only facts provided by the staff member. Do not invent ingredients, "
            "allergens, health claims, cooking methods, or dietary claims. "
            "If details are sparse, stay concise. Return only the description."
        ),
        "input": f"Dish title: {data['title']}\nStaff draft: {data['draft']}",
    }
    api_request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(api_request, timeout=20) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        raise DomainError("AI_UNAVAILABLE", "The AI suggestion could not be generated. Try again shortly.", 502)
    description = _response_text(result)
    if not description:
        raise DomainError("AI_EMPTY_RESPONSE", "The AI returned no description. Try again.", 502)
    return Response({"description": description[:800]})
