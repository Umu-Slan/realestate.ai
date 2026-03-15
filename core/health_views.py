"""
Health and status endpoints for ops and monitoring.
"""
from typing import Any

from django.db import connection
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache


def _ok(name: str, extra: dict = None) -> dict:
    d = {"status": "ok", "check": name}
    if extra:
        d.update(extra)
    return d


def _fail(name: str, error: str) -> dict:
    return {"status": "fail", "check": name, "error": error}


def run_health_checks() -> tuple[dict, int]:
    """
    Run all health checks. Returns (checks_dict, ok_count).
    Used by health_all and operations view.
    """
    checks = {}
    ok_count = 0

    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        checks["db"] = _ok("db")
        ok_count += 1
    except Exception as e:
        checks["db"] = _fail("db", str(e))

    try:
        import redis
        from django.conf import settings
        r = redis.from_url(getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6380/1"))
        r.ping()
        checks["redis"] = _ok("redis")
        ok_count += 1
    except Exception as e:
        checks["redis"] = _fail("redis", str(e))

    try:
        with connection.cursor() as c:
            c.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            if c.fetchone():
                checks["vector"] = _ok("vector")
                ok_count += 1
            else:
                checks["vector"] = _fail("vector", "pgvector not installed")
    except Exception as e:
        checks["vector"] = _fail("vector", str(e))

    from django.conf import settings
    if getattr(settings, "DEMO_MODE", False):
        checks["model"] = _ok("model", {"mode": "demo"})
        ok_count += 1
    elif getattr(settings, "OPENAI_API_KEY", ""):
        checks["model"] = _ok("model", {"mode": "live"})
        ok_count += 1
    else:
        checks["model"] = _fail("model", "OPENAI_API_KEY not set")

    return checks, ok_count


@require_GET
@never_cache
def health_db(request):
    """Database connectivity check."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return JsonResponse(_ok("db"))
    except Exception as e:
        return JsonResponse(_fail("db", str(e)), status=503)


@require_GET
@never_cache
def health_redis(request):
    """Redis connectivity check (uses CELERY_BROKER_URL)."""
    try:
        from django.conf import settings
        import redis
        url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6380/1")
        r = redis.from_url(url)
        r.ping()
        return JsonResponse(_ok("redis"))
    except ImportError:
        return JsonResponse(_fail("redis", "redis package not installed"), status=503)
    except Exception as e:
        return JsonResponse(_fail("redis", str(e)), status=503)


@require_GET
@never_cache
def health_celery(request):
    """Celery worker availability (optional - may not be required for local demo)."""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        if stats:
            return JsonResponse(_ok("celery", {"workers": len(stats)}))
        return JsonResponse(_ok("celery", {"workers": 0, "note": "No workers (local demo ok)"}))
    except ImportError:
        return JsonResponse(_ok("celery", {"note": "Celery not configured - local demo mode"}))
    except Exception as e:
        return JsonResponse(_fail("celery", str(e)), status=503)


@require_GET
@never_cache
def health_vector(request):
    """Vector search readiness (pgvector)."""
    try:
        from django.db import connection
        with connection.cursor() as c:
            c.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            row = c.fetchone()
        if not row:
            return JsonResponse(_fail("vector", "pgvector extension not installed"), status=503)
        return JsonResponse(_ok("vector"))
    except Exception as e:
        return JsonResponse(_fail("vector", str(e)), status=503)


@require_GET
@never_cache
def health_model(request):
    """Model provider config presence (API key, etc.)."""
    from django.conf import settings
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    demo_mode = getattr(settings, "DEMO_MODE", False)
    if demo_mode:
        return JsonResponse(_ok("model", {"mode": "demo", "note": "Mock LLM"}))
    if not api_key:
        return JsonResponse(_fail("model", "OPENAI_API_KEY not set"), status=503)
    return JsonResponse(_ok("model", {"mode": "live"}))


@require_GET
@never_cache
def health_all(request):
    """Aggregated health - all checks."""
    checks, ok_count = run_health_checks()
    status = 200 if ok_count >= 2 else 503
    return JsonResponse({"checks": checks, "summary": f"{ok_count}/4 ok"}, status=status)


@require_GET
@never_cache
def health_ready(request):
    """
    Readiness probe: DB-only. Use for load balancers / k8s readiness.
    If DB is up, the app can accept traffic.
    """
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return JsonResponse({"status": "ready", "check": "db"})
    except Exception as e:
        return JsonResponse({"status": "not_ready", "check": "db", "error": str(e)}, status=503)
