"""
Django settings for Real Estate AI System v0.
"""
import os
from pathlib import Path

import environ

env = environ.Env(
    DEBUG=(bool, True),
    DEMO_MODE=(bool, True),
    DJANGO_ENV=(str, "development"),
)

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(str(env_file))

SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-change-in-production")
# Safe DEBUG: force False when SECRET_KEY is dev default or DJANGO_ENV=production
_django_env = env("DJANGO_ENV")
_unsafe_secret = SECRET_KEY in ("dev-secret-key-change-in-production", "change-this-in-production")
DEBUG = False if (_django_env == "production" or _unsafe_secret) else env("DEBUG")
_allowed = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "testserver"])
# Vercel: allow all *.vercel.app deployment URLs (preview + production)
_is_vercel = os.environ.get("VERCEL") == "1" or env.bool("VERCEL", default=False)
if _is_vercel:
    _allowed.extend([".vercel.app", os.environ.get("VERCEL_URL", "")])
ALLOWED_HOSTS = list(dict.fromkeys(h for h in _allowed if h))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    # Modular monolith apps
    "core",
    "companies",
    "accounts",
    "crm",
    "conversations",
    "knowledge",
    "leads",
    "support",
    "orchestration",
    "scoring",
    "intelligence",
    "engines",
    "console",
    "recommendations",
    "integrations",
    "channels",
    "audit",
    "improvement",
    "evaluation",
    "demo",
    "onboarding",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.CorrelationIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware_auth.AuthRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "console" / "templates"), str(BASE_DIR / "accounts" / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "console.context_processors.console_stats",
            ],
        },
    },
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgresql://realestate_dev:realestate_dev_pass@localhost:5433/realestate_ai",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("LANGUAGE_CODE", default="ar")
LANGUAGES = [
    ("ar", "العربية"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[]) if not DEBUG else []

# Auth - login redirect to operator console
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/console/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Session hardening
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_HTTPONLY = False  # JS needs to read for AJAX
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6380/1")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6380/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

DEMO_MODE = env("DEMO_MODE")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")

# WhatsApp Business API webhook verification
WHATSAPP_VERIFY_TOKEN = env("WHATSAPP_VERIFY_TOKEN", default="")
LLM_MODEL = env("LLM_MODEL", default="gpt-4o-mini")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="text-embedding-3-small")

# Observability: structured logging for pipeline events
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "observability": {
            "()": "core.observability.ObservabilityFormatter",
            "format": "%(asctime)s [%(levelname)s] %(name)s %(message)s",
        },
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "observability",
        },
    },
    "loggers": {
        "realestate.observability": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
