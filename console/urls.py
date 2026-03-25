from django.urls import path, include
from django.views.generic import RedirectView

from . import views

app_name = "console"

urlpatterns = [
    path("notifications/", views.notifications, name="notifications"),
    path("search/", views.search, name="search"),
    path("", views.dashboard, name="dashboard"),
    path("analytics/", views.analytics, name="analytics"),
    path("intelligence/", views.lead_intelligence, name="lead_intelligence"),
    path("conversations/", views.conversations, name="conversations"),
    path("conversations/<int:pk>/", views.conversation_detail, name="conversation_detail"),
    path("customers/", views.customers, name="customers"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("scoring/", views.lead_scoring, name="lead_scoring"),
    path("scoring/export/", views.lead_scoring_export, name="lead_scoring_export"),
    path("support/", views.support_cases, name="support_cases"),
    path("support/<int:pk>/", views.support_case_detail, name="support_case_detail"),
    path("escalations/", views.escalations, name="escalations"),
    path("escalations/<int:pk>/", views.escalation_detail, name="escalation_detail"),
    path("recommendations/", views.recommendations_view, name="recommendations"),
    path("knowledge/", views.knowledge, name="knowledge"),
    path("knowledge/<int:pk>/", views.knowledge_doc_detail, name="knowledge_doc_detail"),
    path("structured-facts/", views.structured_facts, name="structured_facts"),
    path("structured-facts/<int:pk>/", views.structured_facts_project, name="structured_facts_project"),
    path("company/", views.company_config, name="company_config"),
    path("audit/", views.audit, name="audit"),
    path("operations/", views.operations, name="operations"),
    path("corrections/", views.corrections, name="corrections"),
    path("improvement/", views.improvement_insights, name="improvement_insights"),
    path("demo/", views.demo_scenarios, name="demo_scenarios"),
    path("demo-scenarios/", RedirectView.as_view(pattern_name="console:demo_scenarios", permanent=False)),
    path("demo/eval/", views.demo_eval_mode, name="demo_eval"),
    path("demo/replay/<int:pk>/", views.demo_replay, name="demo_replay"),
    path("sales-eval/", views.sales_eval, name="sales_eval"),
    path("sales-eval/run/<str:run_id>/", views.sales_eval_run_detail, name="sales_eval_run_detail"),
    path("api/feedback/", views.submit_feedback, name="submit_feedback"),
    path("api/correction/", views.submit_correction, name="submit_correction"),
]
