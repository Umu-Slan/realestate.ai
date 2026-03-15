from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.i18n import set_language

urlpatterns = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/", include("core.api_urls")),
    path("health/", include("core.health_urls")),
    path("console/", include("console.urls")),
    path("console/onboarding/", include("onboarding.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
