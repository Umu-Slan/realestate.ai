"""
Seed sample escalations with realistic handoff summaries for demo/showcase.
Uses existing customers and conversations when available; creates minimal if none exist.
Run: python manage.py seed_escalations
     python manage.py seed_escalations --replace   # Clear existing first, then seed
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from companies.services import get_default_company
from leads.models import Customer, CustomerIdentity
from conversations.models import Conversation, Message
from support.models import Escalation
from core.enums import (
    EscalationReason,
    EscalationStatus,
    SourceChannel,
    CustomerType,
)

# Sample escalations with realistic handoff data
ESCALATION_SAMPLES = [
    {
        "reason": EscalationReason.ANGRY_CUSTOMER,
        "status": EscalationStatus.OPEN,
        "handoff": {
            "customer_identity": {"name": "أحمد محمود", "phone": "+201012345678", "email": "ahmed.mahmoud@example.com"},
            "intent": {"primary": "support_complaint", "secondary": ["delivery_inquiry"], "summary": "شكوى - تأخر تسليم الشقة"},
            "intent_summary": "شكوى - تأخر تسليم الشقة (Delivery inquiry + complaint)",
            "qualification_summary": "Budget: 2,500,000-3,000,000 EGP; Location: Sheikh Zayed; Type: apartment",
            "score_and_category": "Score: 72 (Warm) | Support: delivery",
            "support_category": "delivery",
            "routing": {"route": "support_escalation", "queue": "delivery_complaints"},
            "risk_notes": ["Customer expressed frustration", "Mentioned legal action if delayed"],
            "recommended_next_step": "Contact delivery team; offer compensation options",
            "conversation_summary": "Customer inquired about delivery date for unit 1201. Delayed 3 months. Expressed anger. Asked for manager contact.",
            "last_message": "أنا محتاج أتكلم مع المسؤول، الوضع ده مش مقبول",
        },
    },
    {
        "reason": EscalationReason.LEGAL_CONTRACT,
        "status": EscalationStatus.IN_PROGRESS,
        "handoff": {
            "customer_identity": {"name": "Sara Johnson", "phone": "+971501234567", "email": "sara.j@example.com"},
            "intent": {"primary": "contract_issue", "secondary": [], "summary": "Contract clause clarification"},
            "intent_summary": "Contract clause clarification (contract_issue)",
            "qualification_summary": "Budget: 4,000,000-5,000,000 EGP; Location: Dubai Hills; Type: villa",
            "score_and_category": "Score: 88 (Hot) | Support: contract",
            "support_category": "contract",
            "routing": {"route": "legal_handoff", "queue": "legal_review"},
            "risk_notes": ["Contract interpretation required", "Clause 12 dispute"],
            "recommended_next_step": "Legal team review; schedule call with contracts manager",
            "conversation_summary": "Customer signed, now questioning clause 12 (penalty terms). Wants modification before final payment.",
            "last_message": "I need legal advice on clause 12 before I proceed",
        },
        "resolution": "Legal team reviewing. Call scheduled for tomorrow 10 AM.",
    },
    {
        "reason": EscalationReason.PRICING_EXCEPTION,
        "status": EscalationStatus.OPEN,
        "handoff": {
            "customer_identity": {"name": "خالد العلي", "phone": "+201098765432", "email": "khalid.ali@example.com"},
            "intent": {"primary": "price_inquiry", "secondary": [], "summary": "Price inquiry - VIP discount request"},
            "intent_summary": "Price inquiry - VIP discount request",
            "qualification_summary": "Budget: 8,000,000-10,000,000 EGP; Location: Marina; Type: penthouse",
            "score_and_category": "Score: 92 (Hot) | VIP flagged",
            "support_category": "",
            "routing": {"route": "sales_handoff", "queue": "vip_sales"},
            "risk_notes": ["Request below list price", "Needs manager approval"],
            "recommended_next_step": "Sales manager approval for 5% discount; prepare VIP package",
            "conversation_summary": "VIP lead asking for special pricing. Ready to close if discount approved.",
            "last_message": "كم الحد الأدنى للخصم لو اكتمل الشراء خلال أسبوع؟",
        },
    },
    {
        "reason": EscalationReason.SEVERE_COMPLAINT,
        "status": EscalationStatus.OPEN,
        "handoff": {
            "customer_identity": {"name": "Fatima Hassan", "phone": "+201055512345", "email": "fatima.h@example.com"},
            "intent": {"primary": "maintenance_issue", "secondary": ["complaint"], "summary": "شكوى - عيوب في التشطيب"},
            "intent_summary": "شكوى - عيوب في التشطيب (Maintenance complaint)",
            "qualification_summary": "Budget: N/A (Existing customer); Location: Palm Residences",
            "score_and_category": "Score: N/A | Support: complaint",
            "support_category": "complaint",
            "routing": {"route": "support_escalation", "queue": "p1_complaints"},
            "risk_notes": ["Photos of defects shared", "Wants refund if not fixed"],
            "recommended_next_step": "P1 SLA - Site visit within 24h; quality team inspection",
            "conversation_summary": "Delivered 2 months ago. Cracks in walls, leaking bathroom. Sent photos. Demands fix or refund.",
            "last_message": "أرسلت الصور، محتاجة حد يشوف الوضع خلال ٢٤ ساعة",
        },
    },
    {
        "reason": EscalationReason.VIP_LEAD,
        "status": EscalationStatus.RESOLVED,
        "handoff": {
            "customer_identity": {"name": "Omar El-Sayed", "phone": "+201077788899", "email": "omar.vip@example.com"},
            "intent": {"primary": "investment_inquiry", "secondary": ["project_inquiry"], "summary": "Project inquiry - bulk purchase"},
            "intent_summary": "Project inquiry - bulk purchase (5 units)",
            "qualification_summary": "Budget: 15,000,000-20,000,000 EGP; Location: New Cairo; Type: investment",
            "score_and_category": "Score: 95 (Hot) | VIP",
            "support_category": "",
            "routing": {"route": "vip_sales", "queue": "enterprise"},
            "risk_notes": [],
            "recommended_next_step": "Direct manager handoff; prepare bulk proposal",
            "conversation_summary": "Investment group representative. Wants 5 units in same building. Asked for bulk pricing.",
            "last_message": "We're ready to move if the numbers work for 5 units",
        },
        "resolution": "Handed to enterprise sales. Proposal sent. Follow-up scheduled.",
        "resolved_at_offset_hours": -12,
    },
    {
        "reason": EscalationReason.LOW_CONFIDENCE,
        "status": EscalationStatus.IN_PROGRESS,
        "handoff": {
            "customer_identity": {"name": "Emma Wilson", "phone": "+971509876543", "email": "emma.w@example.com"},
            "intent": {"primary": "installment_inquiry", "secondary": ["documentation_inquiry"], "summary": "Complex multi-intent: installment + residency rules"},
            "intent_summary": "Complex multi-intent: installment + residency rules",
            "qualification_summary": "Budget: 1,800,000-2,200,000 EGP; Location: Business Bay; Type: studio",
            "score_and_category": "Score: 65 (Warm) | Low confidence",
            "support_category": "",
            "routing": {"route": "human_review", "queue": "clarification"},
            "risk_notes": ["Non-resident payment terms unclear", "Mixed Arabic/English"],
            "recommended_next_step": "Clarify residency status; explain installment options for non-residents",
            "conversation_summary": "Asking about installments as non-resident. Also asked about visa. AI response uncertain.",
            "last_message": "So can I get installments if I'm not living in UAE?",
        },
    },
]


class Command(BaseCommand):
    help = "Seed sample escalations with handoff summaries for demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Clear existing escalations before seeding",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            from companies.services import ensure_default_company

            company = get_default_company() or ensure_default_company()

            if options["replace"]:
                count = Escalation.objects.count()
                Escalation.objects.all().delete()
                self.stdout.write(f"Cleared {count} existing escalation(s).")

            customers = list(Customer.objects.filter(company=company).select_related("identity")[:10])
            if not customers:
                customers = self._create_minimal_customers(company)

            conversations = list(
                Conversation.objects.filter(company=company, customer__in=customers)
                .select_related("customer")[:10]
            )
            if not conversations:
                conversations = self._create_minimal_conversations(company, customers)

            created = 0
            for i, sample in enumerate(ESCALATION_SAMPLES):
                cust = customers[i % len(customers)]
                conv = next((c for c in conversations if c.customer_id == cust.id), conversations[0])

                Escalation.objects.create(
                    customer=cust,
                    conversation=conv,
                    reason=sample["reason"].value,
                    status=sample["status"].value,
                    handoff_summary=sample["handoff"],
                    resolution=sample.get("resolution", ""),
                    resolved_at=(
                        timezone.now() - timezone.timedelta(hours=sample["resolved_at_offset_hours"])
                        if sample.get("resolved_at_offset_hours")
                        else None
                    ),
                )
                created += 1

            self.stdout.write(self.style.SUCCESS(f"Created {created} sample escalation(s)."))

    def _create_minimal_customers(self, company):
        identities = [
            ("seed_esc_1", "أحمد محمود", "+201012345678"),
            ("seed_esc_2", "Sara Johnson", "+971501234567"),
            ("seed_esc_3", "خالد العلي", "+201098765432"),
        ]
        customers = []
        for ext_id, name, phone in identities:
            ident, _ = CustomerIdentity.objects.get_or_create(
                external_id=ext_id,
                defaults={"name": name, "phone": phone, "email": f"{ext_id}@example.com"},
            )
            cust, _ = Customer.objects.get_or_create(
                identity=ident,
                company=company,
                defaults={
                    "source_channel": SourceChannel.WEB.value,
                    "customer_type": CustomerType.NEW_LEAD.value,
                    "is_active": True,
                },
            )
            customers.append(cust)
        self.stdout.write(f"Created {len(customers)} minimal customer(s) for escalations.")
        return customers

    def _create_minimal_conversations(self, company, customers):
        convs = []
        for cust in customers[:3]:
            conv = Conversation.objects.create(
                customer=cust,
                company=company,
                channel=SourceChannel.WEB.value,
                status="active",
            )
            Message.objects.create(
                conversation=conv,
                role="user",
                content="Sample message for escalation demo.",
            )
            convs.append(conv)
        self.stdout.write(f"Created {len(convs)} minimal conversation(s) for escalations.")
        return convs
