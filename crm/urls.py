from django.urls import path
from . import views

urlpatterns = [
    path("import/", views.import_crm),
    path("import/summary/", views.import_summary),
]
