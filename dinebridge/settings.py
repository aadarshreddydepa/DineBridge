"""DineBridge API settings. SQL migrations in db/ own the business schema."""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [s.strip() for s in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if s.strip()]

INSTALLED_APPS = ["api", "corsheaders", "rest_framework"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
ROOT_URLCONF = "dinebridge.urls"
ASGI_APPLICATION = "dinebridge.asgi.application"
WSGI_APPLICATION = "dinebridge.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
APPEND_SLASH = False

if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=60)}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "dinebridge"),
        "USER": os.environ.get("POSTGRES_USER", "dinebridge"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "api.errors.exception_handler",
}

CORS_ALLOWED_ORIGINS = [s.strip() for s in os.environ.get("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if s.strip()]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [s.strip() for s in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if s.strip()]
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
QR_PUBLIC_BASE_URL = os.environ.get("QR_PUBLIC_BASE_URL", "").rstrip("/")
ASSET_BASE_URL = os.environ.get("ASSET_BASE_URL", "")
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "uploads"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
