"""
Import CRM from CSV/Excel. Uses adapter-friendly import service.
"""
from django.core.management.base import BaseCommand

from crm.services.import_service import import_crm_file


class Command(BaseCommand):
    help = "Import CRM leads from CSV or Excel"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--auto-merge-threshold", type=float, default=0.95)

    def handle(self, *args, **options):
        path = options["file"]
        dry_run = options["dry_run"]
        threshold = options["auto_merge_threshold"]

        try:
            stats = import_crm_file(path, dry_run=dry_run, auto_merge_threshold=threshold)
            self.stdout.write(f"Total: {stats['total_rows']}, Imported: {stats['imported']}, Duplicates: {stats['duplicates']}, Conflicts: {stats['conflicts']}, Errors: {stats['errors']}")
            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run - no changes committed"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Batch: {stats['batch_id']}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
            raise
