"""Shared language detection for response selection (ar/en)."""


def detect_response_language(text: str) -> str:
    """Detect if text is primarily Arabic or English. Returns 'ar' or 'en'."""
    if not text:
        return "en"
    ar_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return "ar" if ar_chars > len(text) * 0.2 else "en"
