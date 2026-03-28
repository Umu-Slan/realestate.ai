from django.urls import path
from . import views

app_name = "channels"

urlpatterns = [
    path("whatsapp/webhook/", views.whatsapp_webhook, name="whatsapp_webhook"),
    path("inbound/", views.unified_inbound, name="unified_inbound"),
]
