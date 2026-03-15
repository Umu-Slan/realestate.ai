"""
Sales pipeline agents - Intent, Entity, Memory, LeadScore, Recommendation, ResponseComposer.
Each agent has a single responsibility and clear input/output contract.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


# --- Intent taxonomy (pipeline spec) ---
PIPELINE_INTENTS = frozenset({
    "buy_property",
    "investment",
    "ask_projects",
    "schedule_visit",
    "general_question",
})


def _map_legacy_intent(legacy: str) -> str:
    """Map existing intent detector output to pipeline intents."""
    lc = (legacy or "").lower()
    if lc in ("property_search", "booking_intent", "negotiation"):
        return "buy_property"
    if lc == "investment_inquiry":
        return "investment"
    if lc in ("project_details", "location_inquiry", "price_inquiry"):
        return "ask_projects"
    if lc == "visit_request":
        return "schedule_visit"
    return "general_question"


# --- IntentAgent ---

@dataclass
class IntentAgentOutput:
    intent: str
    confidence: float


class IntentAgent:
    """Classify user intent: buy_property | investment | ask_projects | schedule_visit | general_question."""

    def run(self, message: str, conversation_history: list) -> IntentAgentOutput:
        try:
            from orchestration.agents.intent_detector import detect_intent
            result = detect_intent(
                message,
                conversation_history=conversation_history or [],
                use_llm=True,
            )
            mapped = _map_legacy_intent(result.legacy_primary or result.intent)
            conf = float(result.confidence) if result.confidence is not None else 0.7
            return IntentAgentOutput(intent=mapped, confidence=min(1.0, max(0, conf)))
        except Exception:
            return IntentAgentOutput(intent="general_question", confidence=0.3)


# --- EntityExtractionAgent ---

@dataclass
class EntityExtractionOutput:
    budget: Optional[float] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    payment_type: Optional[str] = None


def _parse_amount(s: str) -> Optional[float]:
    """Extract numeric amount (EGP)."""
    if not s:
        return None
    s = str(s).replace(",", "").replace(" ", "")
    arabic = "٠١٢٣٤٥٦٧٨٩"
    for i, a in enumerate(arabic):
        s = s.replace(a, str(i))
    m = re.search(r"[\d.]+", s)
    if not m:
        return None
    try:
        val = float(m.group())
        if "مليون" in s or "million" in s.lower() or "m" == s[-1:].lower():
            val *= 1_000_000
        elif "ألف" in s or "الف" in s or "k" in s.lower():
            val *= 1_000
        return val
    except Exception:
        return None


class EntityExtractionAgent:
    """Extract budget, location, property_type, bedrooms, payment_type from message."""

    def run(self, message: str) -> EntityExtractionOutput:
        t = (message or "").strip()
        out = EntityExtractionOutput()

        # Budget
        budget_pat = r"(?:حوالي|about|تقريباً|ميزانيتي|ميزانيتي حوالي|my budget|budget)?\s*(\d+(?:\.\d+)?)\s*(?:مليون|million|مليونين|ألف|الف|k|m|م)"
        if m := re.search(budget_pat, t, re.IGNORECASE | re.UNICODE):
            amt = _parse_amount(m.group(0))
            if amt:
                out.budget = amt

        # Location
        loc_pat = r"(?:في|منطقة|location|أفضل|فيين|في أي|in)\s+([^\s,،.]+(?:\s+[^\s,،.]+)?)"
        if m := re.search(loc_pat, t, re.IGNORECASE | re.UNICODE):
            out.location = m.group(1).strip()
        # Standalone area names
        areas = ["الشيخ زايد", "القاهرة الجديدة", "المعادي", "أكتوبر", "الشروق", "السادات",
                 "sheikh zayed", "new cairo", "maadi", "october", "shorouk", "zayed"]
        for a in areas:
            if a.lower() in t.lower():
                out.location = a
                break

        # Property type
        type_map = [
            ("شقة", "apartment"), ("فيلا", "villa"), ("استوديو", "studio"),
            ("دوبلكس", "duplex"), ("apartment", "apartment"), ("villa", "villa"),
            ("studio", "studio"), ("duplex", "duplex"),
        ]
        for ar, en in type_map:
            if ar in t or en in t.lower():
                out.property_type = en
                break

        # Bedrooms
        bed_pat = r"(?:غرف|غرفة|غرفتين|ثلاث غرف|bedroom|bedrooms)\s*[:\s]*(\d+)"
        if m := re.search(bed_pat, t, re.IGNORECASE | re.UNICODE):
            try:
                out.bedrooms = int(m.group(1))
            except (ValueError, IndexError):
                pass
        if "استوديو" in t or "studio" in t.lower():
            out.bedrooms = 0

        # Payment type
        if any(x in t.lower() for x in ["تقسيط", "installment", "قسط"]):
            out.payment_type = "installment"
        elif any(x in t.lower() for x in ["كاش", "cash", "نقدي"]):
            out.payment_type = "cash"

        return out


# --- ConversationMemoryAgent ---

@dataclass
class ConversationState:
    intent: str = ""
    budget: Optional[float] = None
    location: Optional[str] = None
    property_type: Optional[str] = None
    payment_type: Optional[str] = None
    stage: str = "qualification"
    lead_score: int = 0
    lead_temperature: str = "cold"

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "budget": self.budget,
            "location": self.location,
            "property_type": self.property_type,
            "payment_type": self.payment_type,
            "stage": self.stage,
            "lead_score": self.lead_score,
            "lead_temperature": self.lead_temperature,
        }


class ConversationMemoryAgent:
    """Merge new entities into state. Never erase previous values."""

    def run(
        self,
        prior_state: Optional[ConversationState],
        intent: str,
        entities: EntityExtractionOutput,
        lead_output: Optional[dict] = None,
    ) -> ConversationState:
        state = ConversationState() if prior_state is None else ConversationState(
            intent=prior_state.intent or intent,
            budget=prior_state.budget,
            location=prior_state.location,
            property_type=prior_state.property_type,
            payment_type=prior_state.payment_type,
            stage=prior_state.stage,
            lead_score=prior_state.lead_score,
            lead_temperature=prior_state.lead_temperature,
        )
        if intent and intent != "general_question":
            state.intent = intent
        if entities.budget is not None:
            state.budget = entities.budget
        if entities.location:
            state.location = entities.location
        if entities.property_type:
            state.property_type = entities.property_type
        if lead_output:
            state.lead_score = lead_output.get("lead_score", state.lead_score)
            state.lead_temperature = lead_output.get("lead_temperature", state.lead_temperature)
        if entities.payment_type:
            state.payment_type = entities.payment_type
        if state.budget and state.location:
            state.stage = "consideration"
        elif state.budget or state.location:
            state.stage = "qualification"
        return state


# --- LeadScoringAgent ---

class LeadScoringAgent:
    """Score lead from state: +20 budget, +20 location, +10 property_type, +10 financing."""

    def run(self, state: ConversationState) -> dict:
        score = 0
        if state.budget is not None:
            score += 20
        if state.location:
            score += 20
        if state.property_type:
            score += 10
        if state.payment_type:
            score += 10
        score = min(100, score)
        if score >= 60:
            temp = "hot"
        elif score >= 40:
            temp = "warm"
        else:
            temp = "cold"
        return {"lead_score": score, "lead_temperature": temp}


# --- RecommendationAgent ---

@dataclass
class RecommendationOutput:
    recommended_projects: list = field(default_factory=list)
    match_scores: list = field(default_factory=list)


class RecommendationAgent:
    """Run only when intent==buy_property AND location AND budget. Filter projects by location and budget."""

    def run(
        self,
        intent: str,
        state: ConversationState,
    ) -> RecommendationOutput:
        if intent != "buy_property":
            return RecommendationOutput()
        if not state.location or state.budget is None:
            return RecommendationOutput()

        try:
            from django.db.models import Q
            from knowledge.models import Project

            loc = (state.location or "").strip()
            budget_val = float(state.budget) if state.budget else None
            if not loc or budget_val is None:
                return RecommendationOutput()

            qs = Project.objects.filter(is_active=True)
            qs = qs.filter(
                Q(location__icontains=loc) | Q(name__icontains=loc) | Q(name_ar__icontains=loc)
            )
            qs = qs.filter(
                Q(price_min__lte=budget_val * 1.2) | Q(price_min__isnull=True)
            )
            qs = qs.filter(
                Q(price_max__gte=budget_val * 0.8) | Q(price_max__isnull=True)
            )
            projects = list(qs[:5])

            recs = []
            scores = []
            for p in projects:
                recs.append({
                    "project_id": p.id,
                    "project_name": p.name,
                    "project_name_ar": getattr(p, "name_ar", "") or p.name,
                    "location": p.location or "",
                    "price_min": float(p.price_min) if p.price_min else None,
                    "price_max": float(p.price_max) if p.price_max else None,
                })
                pmax = float(p.price_max) if p.price_max else float(p.price_min or 0)
                pmin = float(p.price_min) if p.price_min else 0
                mid = (pmin + pmax) / 2 if (pmin or pmax) else 0
                fit = 1.0 - abs(mid - budget_val) / (budget_val or 1) if budget_val else 0.8
                scores.append(min(1.0, max(0, fit)))

            return RecommendationOutput(recommended_projects=recs, match_scores=scores)
        except Exception:
            return RecommendationOutput()


# --- ResponseComposerAgent ---

class ResponseComposerAgent:
    """Combine intent, state, projects, lead_temp into natural response. Never output internal instructions."""

    def run(
        self,
        message: str,
        intent: str,
        state: ConversationState,
        recommendations: RecommendationOutput,
        lead_temperature: str,
    ) -> str:
        if recommendations.recommended_projects:
            # Show projects
            names = [p.get("project_name_ar") or p.get("project_name") or "المشروع" for p in recommendations.recommended_projects[:3]]
            return f"ممتاز! ميزانيتك في {state.location} تفتح خيارات كويسة. من الأنسب لك: {', '.join(names)}. هل تحب تفاصيل عن مشروع معين؟"
        if lead_temperature == "hot" and state.budget and state.location:
            return "مش مستنى تيجي تعاين؟ ممكن نحدد معاك وقت زيارة. أي يوم يناسبك؟"
        if state.budget and not state.location:
            return "ميزانية مناسبة. هل تفضل منطقة معينة؟ مثلاً الشيخ زايد، القاهرة الجديدة، أو المعادي؟"
        if state.location and not state.budget:
            return f"تمام، {state.location} منطقة كويسة. ما الميزانية التقريبية اللي تناسبك؟"
        if intent == "schedule_visit":
            return "أهلاً! نواعدك لمعاينة. أي يوم يناسبك؟ ومين المنطقة اللي مهتم بيها؟"
        if intent == "investment":
            return "استثمار عقاري قرار ذكي. عشان أرشح لك الأنسب: ما الميزانية والمنطقة اللي تفكر فيها؟"
        if intent == "buy_property":
            return "أهلاً! عشان أرشح لك شقق أو فلل تناسبك: ما الميزانية التقريبية والمنطقة المفضلة؟"
        return "أهلاً! كيف أستطيع مساعدتك؟ لو تحب نضيق الخيارات: ما الميزانية والمنطقة اللي تفضلهم؟"
