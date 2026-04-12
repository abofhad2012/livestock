import os

import dj_database_url

from .settings import *


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = False

# يدعم بيئتك المحلية وRender
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY or SECRET_KEY")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

STATIC_ROOT = BASE_DIR / "staticfiles"

_existing_storages = globals().get("STORAGES") or {}
STORAGES = {
    **_existing_storages,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
    _middleware = list(MIDDLEWARE)
    try:
        i = _middleware.index("django.middleware.security.SecurityMiddleware")
        _middleware.insert(i + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
    except ValueError:
        _middleware.insert(0, "whitenoise.middleware.WhiteNoiseMiddleware")
    MIDDLEWARE = _middleware

render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

_allowed_hosts = {
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
}
if render_host:
    _allowed_hosts.add(render_host)

_allowed_hosts.update({"127.0.0.1", "localhost"})
ALLOWED_HOSTS = sorted(_allowed_hosts)

_csrf_trusted = {
    u.strip()
    for u in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if u.strip()
}
if render_url:
    _csrf_trusted.add(render_url)

CSRF_TRUSTED_ORIGINS = sorted(_csrf_trusted)

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")