"""
Verify pytesseract + Tesseract binary (used for image OCR on ingest).
"""
from django.core.management.base import BaseCommand

from knowledge.ocr_runtime import get_ocr_status


class Command(BaseCommand):
    help = "Check Tesseract OCR availability (pytesseract + tesseract binary)"

    def handle(self, *args, **options):
        s = get_ocr_status()
        self.stdout.write(f"pytesseract (Python): {'yes' if s['pytesseract'] else 'no'}")
        self.stdout.write(f"Tesseract (binary):    {'yes' if s['tesseract'] else 'no'}")
        if s.get("version"):
            self.stdout.write(f"Version:               {s['version']}")
        if s.get("configured_lang"):
            self.stdout.write(f"TESSERACT_LANG:        {s['configured_lang']}")
        if s.get("installed_langs"):
            langs = ", ".join(s["installed_langs"][:40])
            more = len(s["installed_langs"]) - 40
            if more > 0:
                langs += f" … (+{more} more)"
            self.stdout.write(f"Installed tessdata:    {langs}")
        if s.get("lang_warnings"):
            for w in s["lang_warnings"]:
                self.stdout.write(self.style.WARNING(f"Lang warning:          {w}"))
        if s.get("lang_list_error"):
            self.stdout.write(self.style.WARNING(f"Could not list langs:  {s['lang_list_error']}"))
        if s.get("error"):
            self.stdout.write(self.style.WARNING(f"Detail:                {s['error']}"))
        self.stdout.write(f"Docs:                  {s.get('doc_path', 'docs/OCR_WINDOWS.md')}")
        if s["tesseract"]:
            self.stdout.write(self.style.SUCCESS("OCR is ready for image ingestion."))
            self.stdout.write("After fixing OCR, re-run parsing: python manage.py reparse_documents --images-only")
        else:
            self.stdout.write(self.style.ERROR("OCR is not fully available — see docs/OCR_WINDOWS.md"))
