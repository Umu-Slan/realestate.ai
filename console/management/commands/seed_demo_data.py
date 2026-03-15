"""
Seed demo data for enterprise-style console showcase.
Creates: 20 customers, 30 conversations, 15 recommendations, 5 support cases.
Projects: Marina Tower, Palm Residences, Dubai Hills Apartments, Downtown Business Bay.
"""
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from companies.services import get_default_company
from leads.models import CustomerIdentity, Customer, LeadScore, LeadQualification
from conversations.models import Conversation, Message
from knowledge.models import Project
from support.models import SupportCase, Escalation
from recommendations.models import Recommendation
from core.enums import (
    LeadTemperature,
    BuyerJourneyStage,
    SourceChannel,
    SupportCategory,
    SupportSeverity,
    SupportStatus,
    EscalationReason,
    EscalationStatus,
    CustomerType,
)

# Realistic Arabic/English names
NAMES = [
    "Ahmed Hassan", "Sara Mohammed", "Omar Khalid", "Fatima Ali", "Youssef Ibrahim",
    "Layla Mahmoud", "Khalid Abdullah", "Noor Hassan", "Mohammed Rashid", "Aisha Saleh",
    "James Wilson", "Emma Thompson", "Oliver Davis", "Sophie Brown", "Liam Johnson",
    "محمد أحمد", "عائشة علي", "خالد محمد", "فاطمة حسن", "عمر إبراهيم",
]

PROJECT_NAMES = [
    ("Marina Tower", "Dubai Marina"),
    ("Palm Residences", "Palm Jumeirah"),
    ("Dubai Hills Apartments", "Dubai Hills"),
    ("Downtown Business Bay", "Business Bay"),
]

SAMPLE_MESSAGES = [
    ("user", "What apartments are available in Marina Tower?"),
    ("assistant", "Marina Tower offers 1–3 bedroom units with views of the marina. Prices start from AED 1.2M. Would you like pricing for a specific unit type?"),
    ("user", "I'm looking for a 2-bedroom under 2 million"),
    ("assistant", "We have 2-bedroom units from AED 1.5M to 1.9M. I can share the brochure. What's your preferred payment plan?"),
    ("user", "Show me projects in Dubai Hills"),
    ("assistant", "Dubai Hills Apartments has excellent family-sized units. Prices range AED 1.8M–3.5M. Shall I send the floor plans?"),
]


class Command(BaseCommand):
    help = "Seed demo data: customers, conversations, projects, recommendations, support cases"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing demo data first")

    def handle(self, *args, **options):
        company = get_default_company()

        # Create projects
        projects = []
        for name, location in PROJECT_NAMES:
            price_min = random.randint(800000, 1200000)
            price_max = price_min + random.randint(500000, 2000000)
            proj, _ = Project.objects.get_or_create(
                name=name,
                company=company,
                defaults={
                    "location": location,
                    "property_types": ["apartment", "villa"],
                    "price_min": Decimal(price_min),
                    "price_max": Decimal(price_max),
                    "is_active": True,
                },
            )
            projects.append(proj)
        self.stdout.write(f"Projects: {[p.name for p in projects]}")

        # Create 20 customers with identities
        customers = []
        used_names = set()
        for i in range(20):
            name = NAMES[i % len(NAMES)]
            if name in used_names:
                name = f"{name} {i}"
            used_names.add(name)
            external_id = f"demo_seed_{i}_{name.replace(' ', '_')}"
            identity, _ = CustomerIdentity.objects.get_or_create(
                external_id=external_id,
                defaults={
                    "name": name,
                    "phone": f"+9715{random.randint(10000000, 99999999)}",
                    "email": f"{external_id}@example.com",
                },
            )
            cust, _ = Customer.objects.get_or_create(
                identity=identity,
                company=company,
                defaults={
                    "source_channel": random.choice([SourceChannel.WEB.value, SourceChannel.WHATSAPP.value, SourceChannel.DEMO.value]),
                    "customer_type": random.choice([CustomerType.NEW_LEAD.value, CustomerType.RETURNING_LEAD.value, CustomerType.EXISTING_CUSTOMER.value]),
                    "is_active": True,
                },
            )
            customers.append(cust)

        self.stdout.write(f"Created {len(customers)} customers")

        # Create 30 conversations (some customers have multiple)
        conversations = []
        now = timezone.now()
        for i in range(30):
            customer = random.choice(customers)
            channel = random.choice([SourceChannel.WEB.value, SourceChannel.WHATSAPP.value, SourceChannel.DEMO.value])
            conv = Conversation.objects.create(
                customer=customer,
                company=company,
                channel=channel,
                status="active",
            )
            created = now - timedelta(hours=random.randint(1, 720))
            Conversation.objects.filter(pk=conv.pk).update(created_at=created)
            conv.refresh_from_db()

            # Add 2–4 messages
            for j, (role, content) in enumerate(random.sample(SAMPLE_MESSAGES, min(4, len(SAMPLE_MESSAGES)))):
                Message.objects.create(
                    conversation=conv,
                    role=role,
                    content=content,
                )
            conversations.append(conv)

        self.stdout.write(f"Created {len(conversations)} conversations")

        # Create 15 recommendations
        for i in range(15):
            cust = random.choice(customers)
            conv = random.choice([c for c in conversations if c.customer_id == cust.id] or conversations)
            proj = random.choice(projects)
            confidence = random.uniform(0.5, 0.95)
            reasons = random.sample(
                ["Matches budget", "Preferred location", "Family-sized apartment", "Payment plan fits", "Near amenities"],
                k=random.randint(2, 4),
            )
            Recommendation.objects.create(
                customer=cust,
                conversation=conv,
                project=proj,
                rationale=f"Strong match based on {', '.join(reasons)}.",
                rank=i + 1,
                metadata={
                    "confidence": confidence,
                    "match_reasons": reasons,
                },
            )

        self.stdout.write("Created 15 recommendations")

        # Create 5 support cases
        for i in range(5):
            cust = random.choice(customers)
            conv = random.choice([c for c in conversations if c.customer_id == cust.id] or conversations)
            category = random.choice(list(SupportCategory)).value
            status = random.choice([SupportStatus.OPEN.value, SupportStatus.IN_PROGRESS.value, SupportStatus.RESOLVED.value])
            SupportCase.objects.create(
                customer=cust,
                conversation=conv,
                category=category,
                summary=f"Demo support case {i+1}: {category} inquiry",
                status=status,
                severity=random.choice(list(SupportSeverity)).value,
            )

        self.stdout.write("Created 5 support cases")

        # Add lead scores for hot/warm/cold distribution
        for cust in customers[:15]:
            temp = random.choice([LeadTemperature.HOT.value, LeadTemperature.WARM.value, LeadTemperature.COLD.value])
            LeadScore.objects.get_or_create(
                customer=cust,
                defaults={
                    "score": random.randint(60, 95),
                    "temperature": temp,
                    "journey_stage": random.choice(list(BuyerJourneyStage)).value,
                    "explanation": [],
                    "rule_version": "v1",
                },
            )

        # Create 2 escalations
        for i in range(2):
            cust = random.choice(customers)
            conv = random.choice([c for c in conversations if c.customer_id == cust.id] or conversations)
            Escalation.objects.create(
                customer=cust,
                conversation=conv,
                reason=random.choice([e.value for e in EscalationReason]),
                status=EscalationStatus.OPEN.value,
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
