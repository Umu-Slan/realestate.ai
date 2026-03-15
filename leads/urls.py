from django.urls import path
from . import views

urlpatterns = [
    path("search/", views.search_customer),
    path("profile/<int:customer_id>/", views.customer_profile),
    path("identity/candidates/", views.identity_candidates),
    path("identity/merge/<int:candidate_id>/approve/", views.merge_approve),
    path("identity/merge/<int:candidate_id>/reject/", views.merge_reject),
]
