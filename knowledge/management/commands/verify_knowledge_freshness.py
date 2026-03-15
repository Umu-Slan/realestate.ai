"""
Verify knowledge freshness: mark stale documents, update last_verified_at.
Usage: python manage.py verify_knowledge_freshness [--mark-stale-after-days 90]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from knowledge.models import IngestedDocument
from core.enums import VerificationStatus
from audit.models import ActionLog
from core.enums import AuditAction


class Command(BaseCommand):
    help = "Verify knowledge freshness and mark stale documents"

    def add_arguments(self, parser):
        parser.add_argument("--mark-stale-after-days", type=int, default=90)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        days = options["mark_stale_after_days"]
        dry_run = options["dry_run"]
        threshold = timezone.now() - timedelta(days=days)

        stale = IngestedDocument.objects.filter(
            status="embedded",
            verification_status=VerificationStatus.UNVERIFIED,
            last_verified_at__isnull=True,
            parsed_at__lt=threshold,
        )
        count = stale.count()
        if dry_run:
            self.stdout.write(f"Would mark {count} documents as stale")
            return

        for doc in stale:
            doc.verification_status = VerificationStatus.STALE
            doc.save(update_fields=["verification_status", "updated_at"])
            ActionLog.objects.create(
                action=AuditAction.KNOWLEDGE_VERIFIED.value,
                subject_type="ingested_document",
                subject_id=str(doc.id),
                payload={"action": "marked_stale", "reason": f"Unverified for {days}+ days"},
            )

        # Also mark docs with validity_window_end in the past
        from django.db.models import Q
        from datetime import date
        expired = IngestedDocument.objects.filter(
            status="embedded",
            validity_window_end__lt=date.today(),
        ).exclude(verification_status=VerificationStatus.STALE)
        for doc in expired:
            doc.verification_status = VerificationStatus.STALE
            doc.save(update_fields=["verification_status", "updated_at"])
            count += 1
            ActionLog.objects.create(
                action=AuditAction.KNOWLEDGE_VERIFIED.value,
                subject_type="ingested_document",
                subject_id=str(doc.id),
                payload={"action": "marked_stale", "reason": "validity_window_end passed"},
            )

        self.stdout.write(self.style.SUCCESS(f"Marked {count} documents as stale"))
