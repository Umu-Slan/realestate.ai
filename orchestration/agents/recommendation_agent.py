"""
Recommendation Agent - production-grade conversion of property matching to customer-ready output.
Selects top candidates, explains why each fits, provides alternatives when fit is weak.
"""
from decimal import Decimal
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import RecommendationAgentOutput, WEAK_FIT_THRESHOLD


def _to_top_recommendation(m: dict) -> dict:
    """Convert match dict to top_recommendation with why_it_matches and tradeoffs."""
    why = list(m.get("match_reasons") or m.get("top_reasons") or [])
    if m.get("rationale") and m["rationale"] not in why:
        why.append(m["rationale"])
    tradeoffs = m.get("trade_offs") or m.get("tradeoffs") or []
    out = dict(m)
    out.setdefault("why_it_matches", why)
    out.setdefault("tradeoffs", tradeoffs)
    return out


class RecommendationAgent:
    name = "recommendation"

    def run(self, context: AgentContext) -> AgentResult:
        """Produce recommendations. Reuse property_matching or run recommend_projects.
        Eligibility: only show recommendations when budget+location known, intent=buy/invest, market supported.
        """
        try:
            qualification = context.get_qualification()
            intent_out = context.intent_output or {}
            intent_primary = intent_out.get("primary", "")
            sales_intent = intent_out.get("sales_intent", "")

            from orchestration.recommendation_eligibility import check_recommendation_eligibility

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

            elig = check_recommendation_eligibility(
                intent_primary=intent_primary,
                sales_intent=sales_intent,
                budget_min=budget_min,
                budget_max=budget_max,
                location_preference=qualification.get("location_preference", ""),
                property_type=qualification.get("property_type", ""),
                response_mode=context.response_mode or "",
            )
            if not elig.recommendation_ready:
                output = RecommendationAgentOutput(
                    matches=[],
                    top_recommendations=[],
                    alternatives=[],
                    qualification_summary="",
                    data_completeness="minimal",
                    overall_confidence=0.0,
                    recommendation_confidence=0.0,
                    response_text="",
                    recommendation_ready=False,
                    recommendation_block_reason=elig.recommendation_block_reason or "not_qualified",
                )
                context.recommendation_output = output.to_dict()
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    metadata={"recommendation_block_reason": elig.recommendation_block_reason},
                )

            prop_match = context.property_matching_output or {}

            # Use property matching if already done; else run recommend_projects
            matches_data = prop_match.get("matches", [])
            qual_summary = prop_match.get("qualification_summary", "")
            data_completeness = prop_match.get("data_completeness", "minimal")
            overall_conf = prop_match.get("overall_confidence", 0.0)
            alternatives = prop_match.get("alternatives", [])
            if not matches_data:
                from engines.recommendation_engine import recommend_projects

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

                result = recommend_projects(
                    budget_min=budget_min,
                    budget_max=budget_max,
                    location_preference=qualification.get("location_preference", ""),
                    property_type=qualification.get("property_type", ""),
                    purpose=qualification.get("purpose", ""),
                    urgency=qualification.get("urgency", ""),
                    limit=5,
                )
                matches_data = [
                    {
                        "project_id": m.project_id,
                        "project_name": m.project_name,
                        "location": m.location or "",
                        "price_min": float(m.price_min) if m.price_min else None,
                        "price_max": float(m.price_max) if m.price_max else None,
                        "rationale": m.rationale,
                        "fit_score": m.fit_score,
                        "match_score": m.fit_score,
                        "match_reasons": m.match_reasons or [],
                        "top_reasons": m.match_reasons or [],
                        "trade_offs": m.trade_offs or [],
                        "tradeoffs": m.trade_offs or [],
                        "confidence": m.confidence,
                        "has_verified_pricing": m.has_verified_pricing,
                        "market_context": getattr(m, "market_context", None),
                    }
                    for m in result.matches
                ]
                qual_summary = result.qualification_summary
                data_completeness = result.data_completeness
                overall_conf = result.overall_confidence
                alternatives = [
                    {
                        "project_id": a.project_id,
                        "project_name": a.project_name,
                        "rationale": a.rationale,
                        "why_it_matches": (a.match_reasons or []) + ([a.rationale] if a.rationale else []),
                        "tradeoffs": getattr(a, "trade_offs", []) or [],
                    }
                    for a in result.alternatives
                ]

            from engines.response_builder import build_recommendation_response
            from engines.recommendation_engine import ProjectMatch

            # Convert dicts to ProjectMatch for response builder
            pm_list = []
            for m in matches_data:
                from decimal import Decimal
                pm_list.append(
                    ProjectMatch(
                        project_id=m["project_id"],
                        project_name=m["project_name"],
                        location=m.get("location", ""),
                        price_min=Decimal(str(m["price_min"])) if m.get("price_min") else None,
                        price_max=Decimal(str(m["price_max"])) if m.get("price_max") else None,
                        rationale=m.get("rationale", ""),
                        fit_score=m.get("fit_score", 0),
                        match_reasons=m.get("match_reasons", []),
                        confidence=m.get("confidence", 0),
                        trade_offs=m.get("trade_offs", []),
                        has_verified_pricing=m.get("has_verified_pricing", False),
                    )
                )
            response_text = build_recommendation_response(
                pm_list, lang=context.lang or "ar", qualification_summary=qual_summary
            )

            # Top recommendations with why_it_matches and tradeoffs per item
            top_recommendations = [_to_top_recommendation(m) for m in matches_data]

            # Enrich alternatives with why_it_matches when available
            alts = []
            for a in alternatives:
                a_dict = a if isinstance(a, dict) else {}
                pid = a_dict.get("project_id")
                if pid is None:
                    continue
                alts.append({
                    "project_id": pid,
                    "project_name": a_dict.get("project_name", ""),
                    "rationale": a_dict.get("rationale", ""),
                    "why_it_matches": a_dict.get("why_it_matches") or ([a_dict.get("rationale")] if a_dict.get("rationale") else []),
                    "tradeoffs": a_dict.get("tradeoffs") or a_dict.get("trade_offs") or [],
                })
            alternatives = alts

            # Surface more alternatives when fit is weak
            top_score = matches_data[0].get("fit_score", 0) if matches_data else 0
            if top_score < WEAK_FIT_THRESHOLD and alternatives:
                alternatives = alternatives[:5]
            else:
                alternatives = alternatives[:3]

            output = RecommendationAgentOutput(
                matches=matches_data,
                top_recommendations=top_recommendations,
                alternatives=alternatives,
                qualification_summary=qual_summary,
                data_completeness=data_completeness,
                overall_confidence=overall_conf,
                recommendation_confidence=overall_conf,
                response_text=response_text,
                recommendation_ready=True,
                recommendation_block_reason="",
            )
            context.recommendation_output = output.to_dict()
            # Ensure market context available to sales strategy when recommendation has matches
            if matches_data and not context.market_context_output:
                projects_ctx = {m.get("project_id", i): m["market_context"] for i, m in enumerate(matches_data) if m.get("market_context")}
                if projects_ctx:
                    context.market_context_output = {"projects": projects_ctx, "project_count": len(projects_ctx)}
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "match_count": len(matches_data),
                    "data_completeness": data_completeness,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
