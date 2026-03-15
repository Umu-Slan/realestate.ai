"""
Ingest documents from a directory or single file.
Usage: python manage.py ingest_documents <path> [--type project_pdf] [--source "Company"] [--project-id 1]
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from knowledge.ingestion import ingest_file
from core.enums import DocumentType
from audit.models import ActionLog
from core.enums import AuditAction


class Command(BaseCommand):
    help = "Ingest documents from path (file or directory)"

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="File or directory path")
        parser.add_argument("--type", default="project_pdf", choices=[c[0] for c in DocumentType.choices])
        parser.add_argument("--source", default="ingestion", help="Source name")
        parser.add_argument("--project-id", type=int, default=None)
        parser.add_argument("--source-of-truth", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["path"])
        doc_type = options["type"]
        source = options["source"]
        project_id = options["project_id"]
        source_of_truth = options["source_of_truth"]
        dry_run = options["dry_run"]

        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Path not found: {path}"))
            return

        files = []
        if path.is_file():
            if path.suffix.lower() in (".pdf", ".csv", ".xlsx", ".xls", ".txt", ".md"):
                files.append(path)
        else:
            for ext in ["*.pdf", "*.csv", "*.xlsx", "*.xls", "*.txt", "*.md"]:
                files.extend(path.glob(ext))

        if not files:
            self.stdout.write("No supported files found.")
            return

        for f in files:
            if dry_run:
                self.stdout.write(f"Would ingest: {f}")
                continue
            try:
                doc = ingest_file(
                    str(f.absolute()),
                    DocumentType(doc_type),
                    source,
                    project_id=project_id,
                    source_of_truth=source_of_truth,
                )
                ActionLog.objects.create(
                    action=AuditAction.KNOWLEDGE_INGESTED.value,
                    subject_type="ingested_document",
                    subject_id=str(doc.id),
                    payload={"path": str(f), "title": doc.title},
                )
                self.stdout.write(self.style.SUCCESS(f"Ingested: {doc.title} (id={doc.id})"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed {f}: {e}"))
