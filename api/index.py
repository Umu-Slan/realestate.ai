"""
Vercel serverless entry point for Django.
Vercel sets VERCEL=1; use env ALLOWED_HOSTS or .vercel.app.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
