from django.urls import path

from . import views

app_name = "onboarding"

urlpatterns = [
    path("", views.onboarding_dashboard, name="dashboard"),
    path("upload/documents/", views.upload_documents, name="upload_documents"),
    path("upload/structured/", views.upload_structured, name="upload_structured"),
    path("upload/crm/", views.upload_crm, name="upload_crm"),
    path("batch/<int:pk>/", views.batch_detail, name="batch_detail"),
    path("reindex/", views.reindex_documents, name="reindex_documents"),
]
