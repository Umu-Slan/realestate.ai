from django.urls import path
from . import views

urlpatterns = [
    path("documents/", views.document_list),
    path("documents/ingest/", views.document_ingest),
    path("documents/reindex/", views.document_reindex),
    path("documents/<int:doc_id>/chunks/", views.document_chunks),
    path("retrieval/test/", views.retrieval_test),
]
