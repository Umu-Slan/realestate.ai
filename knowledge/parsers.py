"""
Document parsers for PDF, CSV, Excel, and plain text.
Egyptian real estate domain.
"""
import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.enums import ContentLanguage, DocumentType


@dataclass
class ParseResult:
    content: str
    language: ContentLanguage
    metadata: dict
    sections: list[dict]  # [{title, content, chunk_type}]


def compute_file_hash(path: str) -> str:
    """SHA256 of file content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def detect_language(text: str) -> ContentLanguage:
    """Heuristic: Arabic script vs Latin."""
    if not text or len(text.strip()) < 10:
        return ContentLanguage.UNKNOWN
    ar_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    total_letters = sum(1 for c in text if c.isalpha())
    if total_letters == 0:
        return ContentLanguage.UNKNOWN
    if ar_chars / total_letters > 0.3:
        if ar_chars / total_letters < 0.9:
            return ContentLanguage.AR_EN
        return ContentLanguage.AR
    return ContentLanguage.EN


def parse_pdf(path: str) -> ParseResult:
    """Extract text from PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            parts = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
            raw = "\n\n".join(parts)
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            raw = "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            return ParseResult("", ContentLanguage.UNKNOWN, {"error": str(e)}, [])
    return _post_process(raw, DocumentType.PROJECT_PDF)


def parse_csv(path: str, document_type: DocumentType = DocumentType.PROJECT_METADATA_CSV) -> ParseResult:
    """Parse CSV for project metadata."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return ParseResult("", ContentLanguage.UNKNOWN, {}, [])
    content = _csv_to_text(rows)
    return ParseResult(
        content,
        detect_language(content),
        {"row_count": len(rows), "columns": list(rows[0].keys()) if rows else []},
        [{"title": "Project Metadata", "content": content, "chunk_type": "project_section"}],
    )


def parse_excel(path: str) -> ParseResult:
    """Parse Excel for project metadata."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for sheet in wb.worksheets:
            rows = [[str(c.value or "") for c in row] for row in sheet.iter_rows()]
            if rows:
                parts.append(f"Sheet: {sheet.title}\n" + _rows_to_text(rows))
        wb.close()
        content = "\n\n".join(parts)
        return ParseResult(
            content,
            detect_language(content),
            {"sheets": [s.title for s in wb.worksheets]},
            [{"title": "Excel Data", "content": content, "chunk_type": "project_section"}],
        )
    except ImportError:
        return ParseResult("", ContentLanguage.UNKNOWN, {"error": "openpyxl not installed"}, [])


def parse_text(path: str) -> ParseResult:
    """Parse plain text."""
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    return _post_process(raw, DocumentType.OTHER)


def parse_image(path: str, document_type: DocumentType = DocumentType.PROJECT_BROCHURE) -> ParseResult:
    """
    Raster images (JPG, PNG, WebP, etc.): optional OCR via pytesseract + Tesseract binary;
    otherwise store metadata + short note so ingestion still succeeds and retrieval can match filenames.
    """
    p = Path(path)
    name = p.name
    try:
        from PIL import Image
    except ImportError:
        return ParseResult(
            "",
            ContentLanguage.UNKNOWN,
            {"error": "Pillow not installed; add Pillow to requirements"},
            [],
        )

    try:
        with Image.open(path) as im:
            w, h = im.size
            fmt = (im.format or "unknown") or "unknown"
            work = im.convert("RGB") if im.mode in ("RGBA", "P", "LA", "CMYK") else im.copy()
            ocr_text = ""
            ocr_meta: dict = {}
            try:
                from knowledge.ocr_runtime import ocr_pil_image

                ocr_text, ocr_meta = ocr_pil_image(work)
            except Exception:
                pass
    except Exception as e:
        return ParseResult("", ContentLanguage.UNKNOWN, {"error": str(e)}, [])

    img_meta = {
        "image": True,
        "width": w,
        "height": h,
        "format": fmt,
    }

    # Short OCR still gets placeholder path; threshold keeps noise out but allows modest extracts
    ocr_min_chars = 25
    if len(ocr_text) >= ocr_min_chars:
        pr = _post_process(ocr_text, document_type)
        pr.metadata.update(
            {
                **img_meta,
                "ocr": True,
                "ocr_lang_used": ocr_meta.get("lang_used"),
                "ocr_langs_tried": ocr_meta.get("langs_tried"),
            }
        )
        return pr

    note_ar = (
        "[صورة — {name}]\n"
        "الأبعاد: {w}×{h} بكسل، الصيغة: {fmt}\n"
        "هذا المستند صورة؛ للبحث النصي الأفضل استخدم PDF بنص قابل للنسخ.\n"
        "لاستخراج نص تلقائي من الصور: ثبّت Tesseract OCR على السيرفر، اضبط TESSERACT_CMD في .env إن لزم، ثم نفّذ: python manage.py check_ocr\n"
        "بعد تفعيل OCR أعد تحليل الملفات القديمة: python manage.py reparse_documents --images-only\n"
    ).format(name=name, w=w, h=h, fmt=fmt)
    if ocr_text:
        note_ar += "\nنص مستخرج (جزئي):\n" + ocr_text[:2000]

    pr = _post_process(note_ar, document_type)
    pr.metadata.update(
        {
            **img_meta,
            "ocr": bool(ocr_text),
            "ocr_lang_used": ocr_meta.get("lang_used"),
            "ocr_langs_tried": ocr_meta.get("langs_tried"),
        }
    )
    if ocr_meta.get("ocr_errors"):
        pr.metadata["ocr_errors"] = ocr_meta["ocr_errors"]
    return pr


def _csv_to_text(rows: list[dict]) -> str:
    lines = []
    for i, row in enumerate(rows[:500]):  # limit
        lines.append(" | ".join(f"{k}: {v}" for k, v in row.items()))
    return "\n".join(lines)


def _rows_to_text(rows: list[list]) -> str:
    return "\n".join(" | ".join(str(c) for c in row) for row in rows[:500])


def _post_process(raw: str, doc_type: DocumentType) -> ParseResult:
    """Extract sections and infer chunk types from structure."""
    content = raw.strip()
    language = detect_language(content)
    sections = _extract_sections(content, doc_type)
    metadata = {"char_count": len(content)}
    return ParseResult(content, language, metadata, sections)


def _extract_sections(content: str, doc_type: DocumentType) -> list[dict]:
    """
    Business-aware section extraction.
    Looks for headings in AR/EN (##, ----, numbered, etc.).
    """
    sections = []
    chunk_type_map = {
        DocumentType.PROJECT_PDF: "project_section",
        DocumentType.CASE_STUDY: "company_achievement",
        DocumentType.ACHIEVEMENT: "company_achievement",
        DocumentType.DELIVERY_HISTORY: "delivery_proof",
        DocumentType.FAQ: "faq_topic",
        DocumentType.SUPPORT_SOP: "support_procedure",
        DocumentType.OBJECTION_HANDLING: "objection_topic",
        DocumentType.CREDIBILITY: "company_achievement",
    }
    default_type = chunk_type_map.get(doc_type, "general")

    # Patterns for section headers (AR and EN)
    header_patterns = [
        r"^#+\s+(.+)$",
        r"^[-=]{3,}\s*$",
        r"^(\d+[\.\)]\s*.+)$",
        r"^([أ-يآة\s]+:.*)$",
        r"^(Payment Plan|خطة الدفع|القسط)\.?:",
        r"^(Amenities|المرافق|المميزات)\.?:",
        r"^(Location|الموقع)\.?:",
        r"^(FAQ|الأسئلة|سؤال)\.?:",
        r"^(Delivery|التسليم|تم التسليم)\.?:",
        r"^(Objection|اعتراض|رد)\.?:",
    ]

    section_map = {
        "payment": "payment_plan",
        "خطة الدفع": "payment_plan",
        "القسط": "payment_plan",
        "amenities": "amenities",
        "المرافق": "amenities",
        "المميزات": "amenities",
        "location": "location",
        "الموقع": "location",
        "faq": "faq_topic",
        "الأسئلة": "faq_topic",
        "سؤال": "faq_topic",
        "delivery": "delivery_proof",
        "التسليم": "delivery_proof",
        "objection": "objection_topic",
        "اعتراض": "objection_topic",
    }

    lines = content.split("\n")
    current_title = ""
    current_content: list[str] = []
    current_type = default_type

    def flush():
        if current_content:
            text = "\n".join(current_content).strip()
            if text:
                sections.append({"title": current_title or "Section", "content": text, "chunk_type": current_type})

    for line in lines:
        matched = False
        for pat in header_patterns:
            m = re.match(pat, line.strip(), re.IGNORECASE)
            if m:
                flush()
                title = m.group(1).strip() if m.lastindex else line.strip()
                current_title = title
                current_content = []
                for k, v in section_map.items():
                    if k.lower() in title.lower():
                        current_type = v
                        break
                else:
                    current_type = default_type
                matched = True
                break
        if not matched:
            current_content.append(line)

    flush()
    if not sections and content:
        sections.append({"title": "Content", "content": content[:8000], "chunk_type": default_type})
    return sections
