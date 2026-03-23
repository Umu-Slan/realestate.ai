"""
Vercel serverless entry point for Django.
Vercel sets VERCEL=1; use env ALLOWED_HOSTS or .vercel.app.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

_wsgi_app = get_wsgi_application()

def _root_rewrite(environ, start_response):
    """Rewrite / and empty path to /api/engines/demo/ before Django sees it."""
    path = environ.get("PATH_INFO", "") or "/"
    if path in ("/", ""):
        environ["PATH_INFO"] = "/api/engines/demo/"
    return _wsgi_app(environ, start_response)

app = _root_rewrite
