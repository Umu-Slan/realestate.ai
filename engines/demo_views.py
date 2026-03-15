"""Demo UI for engines - sales, support, recommendation."""
from django.shortcuts import render


def demo_page(request):
    """Render demo HTML page. Touches session to ensure cookie is set for subsequent POSTs."""
    if hasattr(request, "session"):
        request.session.setdefault("demo_initialized", True)
    return render(request, "engines/demo.html")
