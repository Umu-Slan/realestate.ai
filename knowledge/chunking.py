"""
Business-aware chunking for Egyptian real estate.
Prefer semantic sections over naive character splits.
"""
from core.enums import ChunkType, ContentLanguage, DocumentType


def chunk_document(
    sections: list[dict],
    document_type: DocumentType,
    max_chars: int = 800,
    overlap: int = 80,
    *,
    verification_status: str = "unverified",
    access_level: str = "internal",
) -> list[dict]:
    """
    Produce chunks from parsed sections.
    Each chunk: {content, chunk_type, section_title, metadata} with retrieval metadata.
    metadata includes document_type, verification_status, access_level for retrieval safety.
    """
    doc_type_val = document_type.value if hasattr(document_type, "value") else str(document_type)
    base_meta = {
        "document_type": doc_type_val,
        "verification_status": verification_status,
        "access_level": access_level,
    }
    chunks = []
    for sec in sections:
        content = sec.get("content", "")
        title = sec.get("title", "")
        ctype = _infer_chunk_type(sec.get("chunk_type"), document_type)
        if len(content) <= max_chars:
            chunks.append({
                "content": content,
                "chunk_type": ctype,
                "section_title": title,
                "metadata": dict(base_meta),
            })
        else:
            sub_chunks = _split_long_content(content, max_chars, overlap)
            for i, sub in enumerate(sub_chunks):
                meta = dict(base_meta)
                meta["sub_index"] = i
                meta["total_subs"] = len(sub_chunks)
                chunks.append({
                    "content": sub,
                    "chunk_type": ctype,
                    "section_title": f"{title} (part {i+1})" if len(sub_chunks) > 1 else title,
                    "metadata": meta,
                })
    return chunks


def _infer_chunk_type(hint: str, doc_type: DocumentType) -> str:
    """Map section hint to ChunkType enum value."""
    mapping = {
        "project_section": ChunkType.PROJECT_SECTION,
        "payment_plan": ChunkType.PAYMENT_PLAN,
        "amenities": ChunkType.AMENITIES,
        "location": ChunkType.LOCATION,
        "company_achievement": ChunkType.COMPANY_ACHIEVEMENT,
        "delivery_proof": ChunkType.DELIVERY_PROOF,
        "faq_topic": ChunkType.FAQ_TOPIC,
        "objection_topic": ChunkType.OBJECTION_TOPIC,
        "support_procedure": ChunkType.SUPPORT_PROCEDURE,
    }
    ct = mapping.get((hint or "").lower(), ChunkType.GENERAL)
    return ct.value if hasattr(ct, "value") else str(ct)


def _split_long_content(content: str, max_chars: int, overlap: int) -> list[str]:
    """Split long content with overlap. Prefer sentence boundaries."""
    if not content or len(content) <= max_chars:
        return [content] if content else []
    parts = []
    sentences = _split_sentences(content)
    current = []
    current_len = 0
    for sent in sentences:
        sent_len = len(sent) + 1
        if current_len + sent_len > max_chars and current:
            parts.append("\n".join(current))
            overlap_sents = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) + 1 <= overlap:
                    overlap_sents.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break
            current = overlap_sents
            current_len = overlap_len
        current.append(sent)
        current_len += sent_len
    if current:
        parts.append("\n".join(current))
    return parts


def _split_sentences(text: str) -> list[str]:
    """Simple sentence split for AR and EN."""
    import re
    text = text.replace("\n", " ")
    parts = re.split(r"[.!?؟。]\s+", text)
    return [p.strip() + "." for p in parts if p.strip()]
