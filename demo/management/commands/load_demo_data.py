"""
Load demo dataset: sample conversations, identities, projects.
Populates operator console with inspectable data: snapshots, scores, support, etc.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from decimal import Decimal

from django.core.management.base import BaseCommand

from companies.services import get_default_company
from leads.models import CustomerIdentity, Customer, LeadScore, LeadQualification, LeadProfile
from conversations.models import Conversation, Message
from knowledge.models import Project, IngestedDocument, DocumentChunk
from support.models import SupportCase, Escalation
from recommendations.models import Recommendation
from audit.models import ActionLog, HumanCorrection
from crm.models import CRMRecord
from core.enums import (
    LeadTemperature,
    BuyerJourneyStage,
    SourceChannel,
    SupportCategory,
    EscalationReason,
    EscalationStatus,
    VerificationStatus,
    ChunkType,
    ContentLanguage,
    DocumentType,
)


class Command(BaseCommand):
    help = "Load demo dataset for v0 operator console"

    def handle(self, *args, **options):
        base = Path(__file__).resolve().parent.parent
        fixtures_dir = base / "fixtures"

        # Sample projects
        projects_data = [
            {
                "name": "مشروع النخيل",
                "location": "القاهرة الجديدة",
                "property_types": ["apartment", "villa"],
                "price_min": 2500000,
                "price_max": 8000000,
            },
            {
                "name": "مشروع الريف",
                "location": "6 أكتوبر",
                "property_types": ["apartment"],
                "price_min": 1500000,
                "price_max": 4000000,
            },
        ]
        company = get_default_company()
        projects = []
        for p in projects_data:
            proj, _ = Project.objects.get_or_create(
                name=p["name"],
                defaults={**p, "company": company},
            )
            projects.append(proj)
        self.stdout.write(f"Loaded {len(projects)} projects")

        # Sample conversations and related data
        conv_path = fixtures_dir / "sample_conversations.json"
        if conv_path.exists():
            with open(conv_path, encoding="utf-8") as f:
                data = json.load(f)
            for idx, item in enumerate(data):
                external_id = item.get("external_id", "demo")
                identity, _ = CustomerIdentity.objects.get_or_create(
                    external_id=external_id,
                    defaults={"name": external_id, "phone": f"+20{1000000000 + idx}", "email": f"demo{idx}@example.com"},
                )
                customer, _ = Customer.objects.get_or_create(
                    identity=identity,
                    company=company,
                    defaults={"source_channel": SourceChannel.DEMO, "customer_type": "new_lead"},
                )
                conv = Conversation.objects.create(customer=customer, company=company)

                messages = item.get("messages", [])
                user_msg = None
                for mi, msg_data in enumerate(messages):
                    msg = Message.objects.create(
                        conversation=conv, role=msg_data["role"], content=msg_data["content"]
                    )
                    if msg_data["role"] == "user":
                        user_msg = msg
                    elif msg_data["role"] == "assistant" and user_msg:
                        self._create_orchestration_snapshot(conv, user_msg, msg, msg_data["content"])
                        user_msg = None

                self._create_lead_data(customer, conv, idx)
                self._create_support_if_needed(customer, idx)
                self._create_escalation_if_needed(customer, conv, idx)
                self._create_recommendations(customer, conv, projects)
                self._create_action_logs(conv)
                self._create_crm_record(customer, idx)

                self.stdout.write(f"Loaded conversation for {external_id}")

        self._create_knowledge_docs(projects)
        self._create_sample_corrections()
        self.stdout.write(self.style.SUCCESS("Demo data loaded (console-ready)"))

    def _create_orchestration_snapshot(self, conv, user_msg, assistant_msg, response):
        from console.models import OrchestrationSnapshot

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        intent = {"primary": "project_inquiry", "secondary": [], "is_support": False, "is_spam": False, "is_broker": False}
        scoring = {
            "score": 72,
            "temperature": LeadTemperature.WARM,
            "next_best_action": "share_pricing_brochure",
        }
        OrchestrationSnapshot.objects.create(
            conversation=conv,
            message=user_msg,
            run_id=run_id,
            intent=intent,
            qualification={"budget_min": 3000000, "budget_max": 4000000, "location": "القاهرة الجديدة"},
            scoring=scoring,
            routing={"customer_type": "new_lead", "route": "sales"},
            retrieval_sources=[{"doc_id": 1, "chunk_index": 0, "score": 0.92, "document_title": "دليل مشروع النخيل"}],
            policy_decision={"applied_policy": "default"},
            actions_triggered=["qualify_lead", "score_lead"],
            next_best_action="share_pricing_brochure",
            response_produced=response,
            customer_type="new_lead",
        )

    def _create_lead_data(self, customer, conv, idx):
        LeadQualification.objects.create(
            customer=customer,
            conversation_id=conv.id,
            budget_min=Decimal("2500000"),
            budget_max=Decimal("4000000"),
            location_preference="القاهرة الجديدة",
            property_type="apartment",
        )
        LeadScore.objects.create(
            customer=customer,
            score=72,
            temperature=LeadTemperature.WARM,
            journey_stage=BuyerJourneyStage.CONSIDERATION,
            explanation=[
                {"factor": "budget_specified", "contribution": 15},
                {"factor": "location_match", "contribution": 20},
                {"factor": "recent_engagement", "contribution": 12},
            ],
            rule_version="v1",
        )

    def _create_support_if_needed(self, customer, idx):
        if idx == 1:
            SupportCase.objects.create(
                customer_id=customer.id,
                category=SupportCategory.GENERAL,
                summary="طلب استفسار عام عن المشروع",
                status="open",
            )

    def _create_escalation_if_needed(self, customer, conv, idx):
        if idx == 0:
            Escalation.objects.create(
                customer=customer,
                conversation=conv,
                reason=EscalationReason.PRICING_REQUEST,
                status=EscalationStatus.OPEN,
            )

    def _create_recommendations(self, customer, conv, projects):
        Recommendation.objects.create(
            customer=customer,
            conversation=conv,
            project=projects[0],
            rationale="مناسب للميزانية والموقع",
            rank=1,
        )

    def _create_action_logs(self, conv):
        ActionLog.objects.create(
            action="orchestration_completed",
            actor="system",
            subject_type="conversation",
            subject_id=str(conv.id),
            payload={"status": "completed"},
        )
        ActionLog.objects.create(
            action="message_processed",
            actor="orchestrator",
            subject_type="conversation",
            subject_id=str(conv.id),
            payload={},
        )

    def _create_crm_record(self, customer, idx):
        CRMRecord.objects.create(
            crm_id=f"demo_crm_{idx}_{uuid.uuid4().hex[:8]}",
            external_phone=customer.identity.phone if customer.identity else "",
            external_email=customer.identity.email if customer.identity else "",
            external_name=customer.identity.name if customer.identity else f"Demo {idx}",
            historical_classification="lead",
            historical_score=72,
            notes="عرض demo",
            project_interest="مشروع النخيل",
            status="active",
            linked_customer_id=customer.id,
        )

    def _create_knowledge_docs(self, projects):
        from django.utils import timezone

        now = timezone.now()
        for proj in projects[:2]:
            doc, created = IngestedDocument.objects.get_or_create(
                title=f"دليل {proj.name}",
                defaults={
                    "project": proj,
                    "document_type": DocumentType.PROJECT_PDF,
                    "source_name": "demo_import",
                    "uploaded_at": now,
                    "verification_status": VerificationStatus.VERIFIED,
                    "status": "chunked",
                    "parsed_content": f"محتويات مشروع {proj.name} بالتفصيل.",
                },
            )
            if created:
                for i, content in enumerate(
                    [f"نظرة عامة على {proj.name}.", f"الموقع: {proj.location}.", "خطط الدفع متاحة."]
                ):
                    DocumentChunk.objects.create(
                        document=doc,
                        chunk_index=i,
                        chunk_type=ChunkType.PROJECT_SECTION,
                        content=content,
                        language=ContentLanguage.AR,
                    )
                self.stdout.write(f"  Knowledge doc: {doc.id}")

    def _create_sample_corrections(self):
        last_msg = Message.objects.filter(role="assistant").order_by("-id").first()
        if last_msg and not HumanCorrection.objects.exists():
            HumanCorrection.objects.create(
                subject_type="message",
                subject_id=str(last_msg.id),
                field_name="response",
                original_value=last_msg.content[:100],
                corrected_value="نص مُصحح من المشغل للتجربة.",
                corrected_by="demo_operator",
                reason="تصحيح تجريبي للواجهة",
            )
