from django.urls import path
from . import views

urlpatterns = [
    path("analyze/", views.classify_and_score),
]
