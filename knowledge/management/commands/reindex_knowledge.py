"""
Reindex knowledge: re-embed all chunks for given documents or all.
Usage: python manage.py reindex_knowledge [--document-ids 1,2,3]
"""
from django.core.management.base import BaseCommand

from knowledge.models import IngestedDocument, DocumentChunk
from knowledge.embedding import embed_chunks
from audit.models import ActionLog
from core.enums import AuditAction


class Command(BaseCommand):
    help = "Reindex (re-embed) knowledge chunks"

    def add_arguments(self, parser):
        parser.add_argument("--document-ids", type=str, default=None, help="Comma-separated document IDs")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        doc_ids = options["document_ids"]
        dry_run = options["dry_run"]

        if doc_ids:
            ids = [int(x.strip()) for x in doc_ids.split(",") if x.strip()]
            docs = IngestedDocument.objects.filter(id__in=ids, status__in=["parsed", "chunked", "embedded"])
        else:
            docs = IngestedDocument.objects.filter(status__in=["parsed", "chunked", "embedded"])

        count = 0
        for doc in docs:
            chunks = list(doc.chunks.all())
            if not chunks:
                continue
            if dry_run:
                self.stdout.write(f"Would reindex {len(chunks)} chunks for doc {doc.id}: {doc.title}")
                count += len(chunks)
                continue
            embed_chunks(chunks)
            doc.status = "embedded"
            doc.save(update_fields=["status", "updated_at"])
            count += len(chunks)
            ActionLog.objects.create(
                action=AuditAction.KNOWLEDGE_REINDEXED.value,
                subject_type="ingested_document",
                subject_id=str(doc.id),
                payload={"chunk_count": len(chunks)},
            )

        self.stdout.write(self.style.SUCCESS(f"Reindexed {count} chunks"))
