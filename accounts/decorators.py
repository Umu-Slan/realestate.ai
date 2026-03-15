"""
Role-based access decorators for console and internal views.
Requires UserProfile with role (admin, operator, reviewer, demo).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages

from accounts.models import Role


def _get_role(request):
    """Get user role from profile. Returns DEMO if no profile."""
    if not request.user.is_authenticated:
        return None
    profile = getattr(request.user, "profile", None)
    if not profile:
        return Role.DEMO  # No profile = readonly
    return profile.role


def role_required(*allowed_roles: str):
    """Require one of the given roles. Use after @login_required."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            role = _get_role(request)
            if role is None:
                return redirect("accounts:login")
            if role not in allowed_roles:
                messages.error(request, "You do not have permission to access this page.")
                return redirect("console:dashboard")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def admin_required(view_func):
    """Require admin role."""
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def _wrapped(request, *args, **kwargs):
        if _get_role(request) != Role.ADMIN:
            messages.error(request, "Admin access required.")
            return redirect("console:dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


def operator_or_above(view_func):
    """Require operator, reviewer, or admin (not demo)."""
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def _wrapped(request, *args, **kwargs):
        role = _get_role(request)
        if role in (Role.DEMO, None):
            messages.error(request, "Operator access required.")
            return redirect("console:dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


def can_submit_correction(view_func):
    """Require auth + can_edit_corrections (admin, operator, reviewer)."""
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def _wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.can_edit_corrections:
            from django.http import JsonResponse
            return JsonResponse({"error": "Permission denied"}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped
