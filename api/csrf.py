from functools import wraps

from django.middleware.csrf import CsrfViewMiddleware


def require_csrf(view):
    """Enforce CSRF inside DRF's otherwise csrf-exempt APIView dispatch."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        django_request = getattr(request, "_request", request)
        response = CsrfViewMiddleware(lambda req: None).process_view(
            django_request, lambda req: None, (), {}
        )
        if response is not None:
            return response
        return view(request, *args, **kwargs)

    return wrapped
