"""
Knowledge API: list, ingest, reindex, inspect chunks, test retrieval.
"""
from pathlib import Path

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from knowledge.models import IngestedDocument, DocumentChunk
from audit.models import ActionLog
from core.enums import AuditAction
from knowledge.ingestion import ingest_file, ingest_from_content
from knowledge.retrieval import retrieve_by_query
from core.enums import DocumentType


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_list(request):
    """List ingested documents with filters."""
    qs = IngestedDocument.objects.all().order_by("-uploaded_at")
    if doc_type := request.query_params.get("document_type"):
        qs = qs.filter(document_type=doc_type)
    if project_id := request.query_params.get("project_id"):
        qs = qs.filter(project_id=project_id)
    data = [
        {
            "id": d.id,
            "title": d.title,
            "document_type": d.document_type,
            "source_name": d.source_name,
            "source_of_truth": d.source_of_truth,
            "status": d.status,
            "verification_status": d.verification_status,
            "uploaded_at": d.uploaded_at.isoformat(),
            "parsed_at": d.parsed_at.isoformat() if d.parsed_at else None,
            "chunk_count": d.chunks.count(),
        }
        for d in qs[:100]
    ]
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_ingest(request):
    """
    Ingest a document.
    Body: { "path": "/abs/path/to/file.pdf" } or { "content": "...", "title": "...", "document_type": "faq" }
    """
    data = request.data
    path = data.get("path")
    content = data.get("content")

    if path:
        path = Path(path)
        if not path.is_absolute():
            path = Path(data.get("base_dir", ".")) / path
        doc = ingest_file(
            str(path),
            DocumentType(data.get("document_type", "project_pdf")),
            data.get("source_name", "api"),
            project_id=data.get("project_id"),
            company_id=data.get("company_id"),
            source_of_truth=data.get("source_of_truth", False),
            uploaded_by=str(request.user),
        )
        ActionLog.objects.create(
            action=AuditAction.KNOWLEDGE_INGESTED.value,
            actor=str(request.user),
            subject_type="ingested_document",
            subject_id=str(doc.id),
            payload={"path": str(path), "title": doc.title, "source": "api"},
        )
    elif content:
        doc = ingest_from_content(
            content,
            DocumentType(data.get("document_type", "faq")),
            data.get("source_name", "api"),
            data.get("title", "Untitled"),
            project_id=data.get("project_id"),
            company_id=data.get("company_id"),
            source_of_truth=data.get("source_of_truth", False),
        )
        ActionLog.objects.create(
            action=AuditAction.KNOWLEDGE_INGESTED.value,
            actor=str(request.user),
            subject_type="ingested_document",
            subject_id=str(doc.id),
            payload={"title": doc.title, "source": "api"},
        )
    else:
        return Response(
            {"error": "Provide path or content"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({
        "id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "chunk_count": doc.chunks.count(),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_reindex(request):
    """Reindex documents. Body: { "document_ids": [1, 2, 3] } or omit for all."""
    from knowledge.embedding import embed_chunks

    ids = request.data.get("document_ids", [])
    docs = IngestedDocument.objects.filter(status__in=["parsed", "chunked", "embedded"])
    if ids:
        docs = docs.filter(id__in=ids)
    count = 0
    for doc in docs:
        chunks = list(doc.chunks.all())
        if chunks:
            embed_chunks(chunks)
            doc.status = "embedded"
            doc.save(update_fields=["status", "updated_at"])
            count += len(chunks)
    return Response({"reindexed_chunks": count})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_chunks(request, doc_id):
    """Inspect chunks for a document."""
    doc = IngestedDocument.objects.filter(id=doc_id).first()
    if not doc:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    chunks = doc.chunks.all().order_by("chunk_index")
    data = [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "chunk_type": c.chunk_type,
            "section_title": c.section_title,
            "content_preview": c.content[:200] + "..." if len(c.content) > 200 else c.content,
            "has_embedding": c.embedding is not None,
        }
        for c in chunks
    ]
    return Response({"document_id": doc_id, "title": doc.title, "chunks": data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retrieval_test(request):
    """
    Test retrieval for a query.
    Body: { "query": "أسعار الشقق في التجمع", "limit": 5, "document_type": "project_pdf" }
    """
    query = request.data.get("query")
    if not query:
        return Response({"error": "query required"}, status=status.HTTP_400_BAD_REQUEST)
    limit = int(request.data.get("limit", 5))
    doc_type = request.data.get("document_type")
    project_id = request.data.get("project_id")

    results = retrieve_by_query(
        query,
        document_type=doc_type,
        project_id=project_id,
        limit=limit,
    )
    data = [
        {
            "chunk_id": r.chunk_id,
            "content_preview": r.content[:300] + "..." if len(r.content) > 300 else r.content,
            "chunk_type": r.chunk_type,
            "section_title": r.section_title,
            "document_title": r.document_title,
            "score": round(r.score, 4),
            "is_fresh": r.is_fresh,
            "can_use_for_exact_pricing": r.can_use_for_exact_pricing,
        }
        for r in results
    ]
    return Response({"query": query, "results": data})
