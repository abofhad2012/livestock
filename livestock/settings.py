"""
Django settings for livestock project (Render-ready).

- Uses Render PostgreSQL via DATABASE_URL (dj-database-url)
- Serves static files with WhiteNoise
- Pulls SECRET_KEY from environment (Render env vars)
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Core security / env ----
# Render docs: set SECRET_KEY from env and disable DEBUG on Render :contentReference[oaicite:0]{index=0}
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-only-change-me")

# DEBUG: default True locally, False on Render (presence of RENDER env var) :contentReference[oaicite:1]{index=1}
_debug_env = os.environ.get("DJANGO_DEBUG")
if _debug_env is None:
    DEBUG = "RENDER" not in os.environ
else:
    DEBUG = _debug_env.strip() == "1"

# On Render, fail fast if SECRET_KEY not set (avoid deploying with django-insecure)
if "RENDER" in os.environ and (not os.environ.get("SECRET_KEY")):
    raise RuntimeError("SECRET_KEY environment variable is required on Render")

# ALLOWED_HOSTS: Render provides RENDER_EXTERNAL_HOSTNAME :contentReference[oaicite:2]{index=2}
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_host:
    ALLOWED_HOSTS.append(render_host)

# Optional: add extra hosts (custom domain) via env
_extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
if _extra_hosts.strip():
    ALLOWED_HOSTS.extend([h.strip() for h in _extra_hosts.split(",") if h.strip()])

# CSRF trusted origins for HTTPS domains (useful for custom domain)
CSRF_TRUSTED_ORIGINS = []
_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins.strip():
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in _csrf_origins.split(",") if o.strip()])
elif render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")

# ---- Applications ----
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "core",
    "accounts",
    "herd",
    "transactions",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise middleware right after SecurityMiddleware :contentReference[oaicite:3]{index=3}
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "livestock.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "livestock.wsgi.application"

# ---- Database ----
# Render docs: use dj-database-url; Render supplies DATABASE_URL :contentReference[oaicite:4]{index=4}
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# ---- Password validation ----
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---- Internationalization ----
LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_TZ = True

# ---- Static files ----
# Render docs + WhiteNoise: STATIC_ROOT + CompressedManifest storage :contentReference[oaicite:5]{index=5}
STATIC_URL = "/static/"

# your dev static source folder
STATICFILES_DIRS = [BASE_DIR / "static"]

# where collectstatic outputs
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise storage backend (hashed filenames + compression) :contentReference[oaicite:6]{index=6}
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---- Media uploads ----
# (تنبيه: على Render الملفات المحلية قد تكون مؤقتة؛ الأفضل Cloudinary أو Disk لاحقاً)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- Production security knobs ----
# Render sits behind a proxy; this helps Django detect HTTPS correctly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Enable these when running behind HTTPS (Render .onrender.com is HTTPS by default)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS is powerful; keep it OFF by default unless you opt-in via env
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(int(os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0")))
    SECURE_HSTS_PRELOAD = bool(int(os.environ.get("SECURE_HSTS_PRELOAD", "0")))