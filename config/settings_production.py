"""
Production settings for Real Estate AI System.
Uses config.settings as base and overrides for production.
Set DJANGO_SETTINGS_MODULE=config.settings_production or use --settings.
"""
import os
from pathlib import Path

from .settings import *  # noqa: F401, F403

# Enforce production-safe DEBUG (use imported SECRET_KEY from base settings)
_env = os.environ
if _env.get("DJANGO_ENV") == "production":
    DEBUG = False
elif SECRET_KEY in ("dev-secret-key-change-in-production", "change-this-in-production"):  # noqa: F405
    DEBUG = False
else:
    DEBUG = _env.get("DEBUG", "false").lower() in ("1", "true", "yes")

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 0  # Enable (e.g. 31536000) when using HTTPS
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False  # Set True when behind HTTPS proxy

# CSRF: required when using HTTPS and AJAX from same-origin or configured origins
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _env.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()] if _env.get("CSRF_TRUSTED_ORIGINS") else []

# Upload safety: cap file size for operator uploads (docs, CSV)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(_env.get("FILE_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))  # 10MB default

# Media: default BASE_DIR/media; override via env if using external storage path
if _env.get("MEDIA_ROOT"):
    MEDIA_ROOT = Path(_env["MEDIA_ROOT"])  # noqa: F405

# Static files: WhiteNoise for production serving
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Database: connection persistence
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["CONN_MAX_AGE"] = 60
