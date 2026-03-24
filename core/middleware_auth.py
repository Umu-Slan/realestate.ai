"""
Require authentication for console and onboarding routes.
Runs after AuthenticationMiddleware. Redirects unauthenticated users to login.
"""
from django.shortcuts import redirect
from django.conf import settings


LOGIN_URL = getattr(settings, "LOGIN_URL", "/accounts/login/")


def _path_requires_auth(path: str) -> bool:
    """True if path should require authentication."""
    if not path:
        return False
    if path.startswith("/accounts/login"):
        return False
    if path.startswith("/accounts/logout"):
        return False
    if path.startswith("/admin/"):
        return False  # Django admin has its own auth
    if path.startswith("/static/"):
        return False
    if path.startswith("/media/"):
        return False
    if path.startswith("/health/"):
        return False
    if path.startswith("/ping/"):
        return False
    if path.startswith("/api/engines/"):
        return False  # Public chat
    if path.startswith("/api/channels/"):
        return False  # Webhooks
    if path.startswith("/console/"):
        # Allow recommendations without auth for debugging
        if path.startswith("/console/recommendations"):
            return False
        return True
    if path.startswith("/onboarding/"):
        return True
    return False


class AuthRequiredMiddleware:
    """
    Redirect unauthenticated users to login when accessing protected paths.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _path_requires_auth(request.path) and not request.user.is_authenticated:
            return redirect(LOGIN_URL + "?next=" + request.path)
        return self.get_response(request)
