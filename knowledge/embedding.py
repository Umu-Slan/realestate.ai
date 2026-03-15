"""
Embedding service - OpenAI or mock for demo.
"""
from django.conf import settings

from knowledge.models import DocumentChunk


def get_embedding_client():
    """Return embedding client - real or mock."""
    if getattr(settings, "DEMO_MODE", False):
        return _MockEmbeddingClient()
    return _OpenAIEmbeddingClient()


def embed_chunks(chunks: list[DocumentChunk]) -> None:
    """Embed chunks in place. Updates embedding field."""
    client = get_embedding_client()
    texts = [c.content for c in chunks]
    embeddings = client.embed(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb
        chunk.save(update_fields=["embedding", "updated_at"])


class _BaseEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class _MockEmbeddingClient(_BaseEmbeddingClient):
    """Mock: returns zero vectors. Semantic search won't work but ingestion succeeds."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        dim = 1536
        return [[0.0] * dim for _ in texts]


class _OpenAIEmbeddingClient(_BaseEmbeddingClient):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
        resp = self.client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in resp.data]
