from django.urls import path
from . import views
from . import demo_views

urlpatterns = [
    path("demo/", demo_views.demo_page),
    path("project/<int:project_id>/", views.project_detail),
    path("conversation/", views.conversation_history),
    path("sales/", views.sales_chat),
    path("support/", views.support_chat),
    path("recommend/", views.recommend),
    path("templates/", views.templates_list),
    path("objection/", views.objection_detect),
]
