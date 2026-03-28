"""
Re-parse ingested documents from the original file on disk (parse → new chunks → embed).
Use after enabling Tesseract / TESSERACT_LANG or upgrading parsers.
This is not the same as reindex_knowledge, which only re-embeds existing chunk text.
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from audit.models import ActionLog
from core.enums import AuditAction
from knowledge.ingestion import reparse_ingested_document
from knowledge.models import IngestedDocument

_IMAGE_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}
)


class Command(BaseCommand):
    help = "Re-parse knowledge documents from stored raw files (OCR / parser upgrades)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--document-ids",
            type=str,
            default=None,
            help="Comma-separated IngestedDocument IDs (default: all with a raw file)",
        )
        parser.add_argument(
            "--images-only",
            action="store_true",
            help="Only documents whose raw file is a raster image (jpg, png, …)",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        doc_ids = options["document_ids"]
        images_only = options["images_only"]
        dry_run = options["dry_run"]

        qs = IngestedDocument.objects.filter(raw_document__isnull=False).select_related(
            "raw_document"
        )

        if doc_ids:
            ids = [int(x.strip()) for x in doc_ids.split(",") if x.strip()]
            qs = qs.filter(id__in=ids)
        else:
            qs = qs.filter(status__in=["parsed", "chunked", "embedded", "failed"])

        ok = err = skipped = 0
        for doc in qs.order_by("id"):
            raw_path = Path(doc.raw_document.file_path)
            if images_only and raw_path.suffix.lower() not in _IMAGE_SUFFIXES:
                skipped += 1
                continue
            if not raw_path.is_file():
                self.stdout.write(
                    self.style.WARNING(f"Skip doc {doc.id} ({doc.title}): file missing {raw_path}")
                )
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"Would reparse doc {doc.id}: {doc.title} ({raw_path.name})")
                ok += 1
                continue
            try:
                reparse_ingested_document(doc)
                doc.refresh_from_db()
                n = doc.chunks.count()
                self.stdout.write(
                    self.style.SUCCESS(f"Reparsed doc {doc.id} → v{doc.version}, {n} chunks")
                )
                ActionLog.objects.create(
                    action=AuditAction.KNOWLEDGE_REPARSED.value,
                    subject_type="ingested_document",
                    subject_id=str(doc.id),
                    payload={"version": doc.version, "chunk_count": n, "path": str(raw_path)},
                )
                ok += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed doc {doc.id} ({doc.title}): {e}")
                )
                err += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Reparsed={ok}, failed={err}, skipped={skipped}"
                + (" (dry-run)" if dry_run else "")
            )
        )
