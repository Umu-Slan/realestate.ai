"""
Tesseract / pytesseract configuration and health checks for image OCR during ingestion.
The Tesseract **binary** is separate from the Python package; on Windows set TESSERACT_CMD if not on PATH.
"""
from __future__ import annotations

from django.conf import settings


def configure_tesseract() -> bool:
    """
    Apply TESSERACT_CMD from Django settings before calling pytesseract.
    Returns True if the pytesseract module is importable (configuration attempted).
    """
    try:
        import pytesseract
    except ImportError:
        return False

    cmd = (getattr(settings, "TESSERACT_CMD", None) or "").strip()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return True


def get_ocr_status() -> dict:
    """
    Status for operator console and management command.
    Keys: pytesseract (bool), tesseract (bool), version (str), error (str), doc_path (str).
    """
    configured_lang = (getattr(settings, "TESSERACT_LANG", None) or "ara+eng").strip()
    out: dict = {
        "pytesseract": False,
        "tesseract": False,
        "version": "",
        "error": "",
        "doc_path": "docs/OCR_WINDOWS.md",
        "configured_lang": configured_lang,
    }
    try:
        import pytesseract
    except ImportError:
        out["error"] = "pytesseract not installed — run: pip install pytesseract"
        return out

    out["pytesseract"] = True
    if not configure_tesseract():
        out["error"] = "Could not configure pytesseract"
        return out

    try:
        ver = pytesseract.get_tesseract_version()
        out["tesseract"] = True
        out["version"] = str(ver)
    except Exception as e:
        msg = str(e).strip() or "Tesseract binary not found or failed to run"
        out["error"] = msg[:500]
        return out

    try:
        out["installed_langs"] = sorted(pytesseract.get_languages())
    except Exception as e:
        out["installed_langs"] = []
        out["lang_list_error"] = str(e)[:300]

    parts = [p.strip() for p in configured_lang.split("+") if p.strip()]
    missing = [p for p in parts if p and p not in out.get("installed_langs", [])]
    if missing:
        out["lang_warnings"] = [f"tessdata missing language pack(s): {', '.join(missing)} — install Arabic data or set TESSERACT_LANG=eng"]
    return out


def ocr_pil_image(image) -> tuple[str, dict]:
    """
    Run Tesseract on a PIL Image (RGB). Tries TESSERACT_LANG, then ara+eng, ara, eng, default.
    Returns (text, meta) where meta includes lang_used, langs_tried, optional errors.
    """
    meta: dict = {"langs_tried": [], "lang_used": None}
    try:
        import pytesseract
    except ImportError:
        return "", {**meta, "error": "pytesseract not installed"}

    if not configure_tesseract():
        return "", {**meta, "error": "tesseract not configured"}

    primary = (getattr(settings, "TESSERACT_LANG", None) or "ara+eng").strip()
    ordered: list[str] = []
    seen_keys: set[str] = set()
    for cand in (primary, "ara+eng", "ara", "eng", ""):
        c = cand.strip()
        key = c or "__default__"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ordered.append(c)

    best_text = ""
    best_len = 0
    best_lang: str | None = None
    errors: list[str] = []
    for lang in ordered:
        meta["langs_tried"].append(lang or "(default)")
        try:
            kwargs = {"lang": lang} if lang else {}
            text = (pytesseract.image_to_string(image, **kwargs) or "").strip()
            if len(text) > best_len:
                best_len = len(text)
                best_text = text
                best_lang = lang or "default"
        except Exception as e:
            errors.append(f"{lang or 'default'}: {str(e)[:120]}")

    meta["lang_used"] = best_lang
    if errors:
        meta["ocr_errors"] = errors[:6]
    return best_text, meta
