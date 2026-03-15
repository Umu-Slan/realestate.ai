"""
Property Matching Agent - finds projects matching qualification criteria.
Wraps engines.recommendation_engine logic for matching (without response building).
"""
from decimal import Decimal
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import PropertyMatch, PropertyMatchingAgentOutput


class PropertyMatchingAgent:
    name = "property_matching"

    def run(self, context: AgentContext) -> AgentResult:
        """Match projects to qualification. Uses recommendation_engine.recommend_projects."""
        try:
            qualification = context.get_qualification()
            budget_min = qualification.get("budget_min")
            budget_max = qualification.get("budget_max")
            try:
                budget_min = Decimal(str(budget_min)) if budget_min else None
            except (TypeError, ValueError):
                budget_min = None
            try:
                budget_max = Decimal(str(budget_max)) if budget_max else None
            except (TypeError, ValueError):
                budget_max = None

            from engines.recommendation_engine import recommend_projects

            intent_entities = (context.intent_output or {}).get("entities") or {}
            bedroom = qualification.get("bedrooms") or qualification.get("bedroom_preference") or intent_entities.get("bedrooms")
            try:
                bedroom_preference = int(bedroom) if bedroom is not None else None
            except (TypeError, ValueError):
                bedroom_preference = None

            journey_stage = ""
            if context.journey_stage_output:
                journey_stage = (context.journey_stage_output.get("stage") or "").strip()

            historical_ids = qualification.get("historical_project_ids") or []
            mem = context.get_memory() if hasattr(context, "get_memory") else {}
            if not historical_ids and mem:
                viewed = mem.get("viewed_projects") or mem.get("recommended_project_ids") or []
                historical_ids = [int(x) for x in viewed if isinstance(x, (int, str)) and str(x).isdigit()][:20]

            result = recommend_projects(
                budget_min=budget_min,
                budget_max=budget_max,
                location_preference=qualification.get("location_preference", ""),
                property_type=qualification.get("property_type", ""),
                purpose=qualification.get("purpose", ""),
                urgency=qualification.get("urgency", ""),
                bedroom_preference=bedroom_preference,
                financing_preference=qualification.get("financing_readiness", "") or qualification.get("financing_preference", ""),
                payment_method=qualification.get("payment_method", ""),
                journey_stage=journey_stage,
                historical_project_ids=historical_ids or None,
                limit=5,
            )

            typed_matches = []
            for i, m in enumerate(result.matches):
                typed_matches.append(
                    PropertyMatch(
                        project_id=m.project_id,
                        project_name=m.project_name,
                        location=m.location or "",
                        price_min=float(m.price_min) if m.price_min else None,
                        price_max=float(m.price_max) if m.price_max else None,
                        rationale=m.rationale,
                        fit_score=m.fit_score,
                        match_reasons=m.match_reasons or [],
                        confidence=getattr(m, "confidence", 0.0),
                        trade_offs=getattr(m, "trade_offs", []) or [],
                        has_verified_pricing=getattr(m, "has_verified_pricing", False),
                        market_context=getattr(m, "market_context", None),
                    )
                )
            alternatives = [
                {"project_id": a.project_id, "project_name": a.project_name, "rationale": a.rationale}
                for a in result.alternatives
            ]
            output = PropertyMatchingAgentOutput(
                matches=typed_matches,
                overall_confidence=result.overall_confidence,
                data_completeness=result.data_completeness,
                qualification_summary=result.qualification_summary,
                alternatives=alternatives,
            )
            context.property_matching_output = output.to_dict()
            # Aggregate market context for sales strategy (only supported facts)
            projects_ctx = {}
            for m in typed_matches:
                if m.market_context and isinstance(m.market_context, dict):
                    pid = m.market_context.get("project_id", m.project_id)
                    projects_ctx[pid] = m.market_context
            if projects_ctx:
                context.market_context_output = {
                    "projects": projects_ctx,
                    "project_count": len(projects_ctx),
                }

            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "match_count": len(typed_matches),
                    "data_completeness": result.data_completeness,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
