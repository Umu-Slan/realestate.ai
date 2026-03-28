"""
Ingestion pipeline: parse -> chunk -> embed -> store.
"""
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from knowledge.models import RawDocument, IngestedDocument, DocumentChunk, DocumentVersion
from knowledge.parsers import (
    parse_pdf,
    parse_csv,
    parse_excel,
    parse_text,
    parse_image,
    compute_file_hash,
    ParseResult,
)
from knowledge.chunking import chunk_document
from knowledge.embedding import embed_chunks
from core.enums import DocumentType, VerificationStatus, AccessLevel


def ingest_file(
    file_path: str,
    document_type: DocumentType,
    source_name: str,
    project_id: int | None = None,
    company_id: int | None = None,
    source_of_truth: bool = False,
    uploaded_by: str = "",
) -> IngestedDocument:
    """
    Full pipeline: create RawDocument -> parse -> create IngestedDocument -> chunk -> embed.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_hash = compute_file_hash(str(path))
    raw, _ = RawDocument.objects.get_or_create(
        file_hash=file_hash,
        defaults={
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "document_type": document_type,
            "source_name": source_name,
            "uploaded_by": uploaded_by,
        },
    )

    now = timezone.now()
    doc = IngestedDocument.objects.create(
        raw_document=raw,
        project_id=project_id,
        company_id=company_id,
        document_type=document_type,
        source_name=source_name,
        title=path.stem,
        source_of_truth=source_of_truth,
        uploaded_at=now,
        status="pending",
        created_by=uploaded_by,
        access_level=AccessLevel.INTERNAL,
    )

    try:
        result = _parse_by_extension(str(path), document_type)
        doc.parsed_content = result.content
        doc.parsed_at = now
        doc.language = result.language
        doc.status = "parsed"
        doc.metadata = {**doc.metadata, **result.metadata}
        doc.save(update_fields=["parsed_content", "parsed_at", "language", "status", "metadata", "updated_at"])

        DocumentVersion.objects.create(
            document=doc,
            version_number=doc.version,
            parsed_content=result.content,
            snapshot_metadata=doc.metadata,
        )

        chunks_data = chunk_document(
            result.sections,
            document_type,
            verification_status=doc.verification_status,
            access_level=doc.access_level,
        )
        for i, c in enumerate(chunks_data):
            chunk = DocumentChunk.objects.create(
                document=doc,
                chunk_index=i,
                chunk_type=c["chunk_type"],
                section_title=c.get("section_title", ""),
                content=c["content"],
                language=doc.language,
                metadata=c.get("metadata", {}),
            )
            # will embed below

        to_embed = list(doc.chunks.all())
        embed_chunks(to_embed)
        doc.status = "embedded"
        doc.save(update_fields=["status", "updated_at"])

    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        doc.save(update_fields=["status", "error_message", "updated_at"])
        raise

    return doc


def _parse_by_extension(path: str, doc_type: DocumentType) -> ParseResult:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".csv":
        return parse_csv(path, doc_type)
    if ext in (".xlsx", ".xls"):
        return parse_excel(path)
    if ext in (".txt", ".md"):
        return parse_text(path)
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"):
        return parse_image(path, doc_type)
    raise ValueError(f"Unsupported file type: {ext}")


def ingest_from_content(
    content: str,
    document_type: DocumentType,
    source_name: str,
    title: str,
    project_id: int | None = None,
    company_id: int | None = None,
    source_of_truth: bool = False,
) -> IngestedDocument:
    """Ingest from inline content (e.g. pasted text, API)."""
    from knowledge.parsers import _post_process

    result = _post_process(content, document_type)
    now = timezone.now()
    doc = IngestedDocument.objects.create(
        document_type=document_type,
        source_name=source_name,
        title=title,
        source_of_truth=source_of_truth,
        uploaded_at=now,
        parsed_at=now,
        parsed_content=result.content,
        language=result.language,
        status="parsed",
        project_id=project_id,
        company_id=company_id,
        access_level=AccessLevel.INTERNAL,
    )
    DocumentVersion.objects.create(
        document=doc,
        version_number=doc.version,
        parsed_content=result.content,
        snapshot_metadata=doc.metadata,
    )
    chunks_data = chunk_document(
        result.sections,
        document_type,
        verification_status=doc.verification_status,
        access_level=doc.access_level,
    )
    for i, c in enumerate(chunks_data):
        chunk = DocumentChunk.objects.create(
            document=doc,
            chunk_index=i,
            chunk_type=c["chunk_type"],
            section_title=c.get("section_title", ""),
            content=c["content"],
            language=doc.language,
            metadata=c.get("metadata", {}),
        )
    to_embed = list(doc.chunks.all())
    embed_chunks(to_embed)
    doc.status = "embedded"
    doc.save(update_fields=["status", "updated_at"])
    return doc


def reparse_ingested_document(ingested: IngestedDocument) -> IngestedDocument:
    """
    Re-run parse → chunk → embed from the stored raw file (RawDocument.file_path).
    Use after enabling Tesseract, changing TESSERACT_LANG, or upgrading parsers.
    Does not replace reindex_knowledge (that only re-embeds existing chunk text).
    """
    if not ingested.raw_document_id:
        raise ValueError(
            "This document has no linked raw file record; upload the file again to ingest."
        )
    path = Path(ingested.raw_document.file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Raw file missing on disk: {path}")

    raw_dt = ingested.document_type
    dt = raw_dt if isinstance(raw_dt, DocumentType) else DocumentType(raw_dt)

    now = timezone.now()
    try:
        with transaction.atomic():
            result = _parse_by_extension(str(path), dt)
            ingested.chunks.all().delete()
            new_ver = (ingested.version or 1) + 1
            ingested.parsed_content = result.content
            ingested.parsed_at = now
            ingested.language = result.language
            ingested.metadata = {**(ingested.metadata or {}), **result.metadata}
            ingested.error_message = ""
            ingested.version = new_ver
            ingested.status = "parsed"
            ingested.save()

            DocumentVersion.objects.create(
                document=ingested,
                version_number=new_ver,
                parsed_content=result.content,
                snapshot_metadata=ingested.metadata,
            )
            chunks_data = chunk_document(
                result.sections,
                dt,
                verification_status=ingested.verification_status,
                access_level=ingested.access_level,
            )
            for i, c in enumerate(chunks_data):
                DocumentChunk.objects.create(
                    document=ingested,
                    chunk_index=i,
                    chunk_type=c["chunk_type"],
                    section_title=c.get("section_title", ""),
                    content=c["content"],
                    language=ingested.language,
                    metadata=c.get("metadata", {}),
                )
            to_embed = list(ingested.chunks.all())
            embed_chunks(to_embed)
            ingested.status = "embedded"
            ingested.save(update_fields=["status", "updated_at"])
    except Exception as e:
        ingested.status = "failed"
        ingested.error_message = str(e)[:2000]
        ingested.save(update_fields=["status", "error_message", "updated_at"])
        raise
    return ingested
