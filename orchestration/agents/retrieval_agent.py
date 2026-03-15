"""
Production Retrieval Agent - hybrid semantic + metadata retrieval.
Retrieves from: project documents, brochures, FAQs, structured facts,
location content, support docs, sales scripts.
Prioritizes: relevance, freshness, verification status.
Prevents irrelevant context pollution via relevance threshold.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import RetrievalAgentOutput, RetrievalSource
from orchestration.retrieval_planner import plan_retrieval

# Min relevance score to include (prevents irrelevant context pollution)
RELEVANCE_THRESHOLD = 0.25
# Max content snippet length per source
SNIPPET_MAX_CHARS = 200


def _build_structured_summary(
    results: list,
    has_verified_pricing: bool,
    has_verified_availability: bool,
) -> str:
    """Build a concise structured summary for downstream agents."""
    parts = []
    if has_verified_pricing:
        parts.append("Verified pricing available from structured layer.")
    if has_verified_availability:
        parts.append("Verified availability available.")
    for r in results[:5]:
        title = getattr(r, "document_title", "") or ""
        dt = getattr(r, "document_type", "") or ""
        sot = getattr(r, "source_of_truth", False)
        if title:
            tag = " [source-of-truth]" if sot else ""
            parts.append(f"- {title} ({dt}){tag}")
    return " ".join(parts) if parts else "No relevant knowledge retrieved."


def _snippet(content: str, max_len: int = SNIPPET_MAX_CHARS) -> str:
    """Truncate to snippet for context injection."""
    if not content:
        return ""
    c = (content or "").strip()
    if len(c) <= max_len:
        return c
    return c[: max_len - 3].rsplit(" ", 1)[0] + "..."


class RetrievalAgent:
    name = "retrieval"

    def run(self, context: AgentContext) -> AgentResult:
        """Plan and execute hybrid retrieval. Prioritize relevance, freshness, verification."""
        try:
            from knowledge.retrieval import (
                retrieve_by_query,
                get_structured_pricing,
                get_structured_availability,
            )

            intent = context.intent_output or {}
            qualification = context.get_qualification()
            memory = context.get_memory()
            profile = memory.get("customer_profile") or {}
            if profile.get("preferred_locations"):
                qual = dict(qualification)
                qual.setdefault("location_preference", ", ".join(profile["preferred_locations"][:3]))
                qualification = qual

            plan = plan_retrieval(
                message_text=context.message_text,
                intent_primary=intent.get("primary", ""),
                project_preference=qualification.get("project_preference", ""),
                project_id=qualification.get("project_id"),
                is_support=bool(intent.get("is_support")),
            )

            retrieval_sources: list[RetrievalSource] = []
            has_verified_pricing = False
            has_verified_availability = False
            retrieval_error = None

            try:
                results = retrieve_by_query(
                    plan.query,
                    document_types=plan.document_types if plan.document_types else None,
                    chunk_types=plan.chunk_types if plan.chunk_types else None,
                    project_id=plan.project_id,
                    limit=plan.limit,
                )

                for r in results:
                    score = getattr(r, "score", 0.0) or 0.0
                    if score < RELEVANCE_THRESHOLD:
                        continue
                    retrieval_sources.append(
                        RetrievalSource(
                            chunk_id=getattr(r, "chunk_id", 0),
                            document_title=getattr(r, "document_title", "") or "",
                            content_snippet=_snippet(getattr(r, "content", "") or ""),
                            relevance_score=score,
                            source_of_truth=bool(getattr(r, "source_of_truth", False)),
                            verification_status=str(getattr(r, "verification_status", "") or ""),
                            is_fresh=bool(getattr(r, "is_fresh", True)),
                            document_type=str(getattr(r, "document_type", "") or ""),
                            chunk_type=str(getattr(r, "chunk_type", "") or ""),
                        )
                    )

                if plan.use_structured_pricing and plan.project_id:
                    pricing = get_structured_pricing(plan.project_id)
                    if pricing and pricing.get("is_verified"):
                        has_verified_pricing = True
                    avail = get_structured_availability(plan.project_id)
                    if avail and avail.get("is_verified"):
                        has_verified_availability = True
            except Exception as e:
                retrieval_error = str(e)
                retrieval_sources = []

            structured_summary = _build_structured_summary(
                retrieval_sources,
                has_verified_pricing,
                has_verified_availability,
            )

            output = RetrievalAgentOutput(
                query=plan.query,
                document_types=list(plan.document_types),
                retrieval_sources=retrieval_sources,
                has_verified_pricing=has_verified_pricing,
                has_verified_availability=has_verified_availability,
                retrieval_error=retrieval_error,
                structured_summary=structured_summary,
            )
            context.retrieval_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "sources_count": len(retrieval_sources),
                    "has_verified_pricing": has_verified_pricing,
                    "retrieval_error": retrieval_error is not None,
                    "source_of_truth_count": output.source_of_truth_count,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))


