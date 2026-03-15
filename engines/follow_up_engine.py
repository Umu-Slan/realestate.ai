"""
Follow-up Engine - generates smart follow-up messages for dormant leads.
Uses: buyer stage, lead score, last discussed projects, time since last interaction.
Types: gentle_reminder, alternative_recommendation, visit_prompt, value_based_follow_up.
Stores as structured records; does NOT auto-send.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

FOLLOW_UP_TYPES = frozenset({
    "gentle_reminder",
    "alternative_recommendation",
    "visit_prompt",
    "value_based_follow_up",
})


@dataclass
class FollowUpRecommendation:
    """Structured follow-up recommendation - stored, not auto-sent."""
    type: str
    message_text: str
    message_text_en: str = ""
    reasoning: str = ""
    priority: int = 0  # Higher = more urgent
    lead_ref: str = ""
    time_since_last_hours: float = 0.0
    buyer_stage: str = ""
    lead_score: int = 0
    last_projects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "message_text": self.message_text,
            "message_text_en": self.message_text_en,
            "reasoning": self.reasoning,
            "priority": self.priority,
            "lead_ref": self.lead_ref,
            "time_since_last_hours": self.time_since_last_hours,
            "buyer_stage": self.buyer_stage,
            "lead_score": self.lead_score,
            "last_projects": list(self.last_projects or []),
        }


def _select_follow_up_type(
    *,
    buyer_stage: str,
    lead_score: int,
    last_projects: list,
    time_since_last_hours: float,
) -> tuple[str, str]:
    """
    Select best follow-up type and reasoning.
    Returns (type, reasoning).
    """
    stage = (buyer_stage or "").lower()
    score = max(0, min(100, int(lead_score or 0)))
    has_projects = bool(last_projects and len(last_projects) > 0)
    hours = max(0.0, float(time_since_last_hours or 0))

    # Visit planning / shortlisting + hot lead + discussed projects -> visit prompt
    if stage in ("visit_planning", "shortlisting", "negotiation") and score >= 60 and has_projects:
        return ("visit_prompt", f"Lead at {stage}, score {score}, discussed projects. Visit prompt to close.")

    # Consideration/shortlisting + projects -> alternative or visit
    if stage in ("consideration", "shortlisting") and has_projects:
        if hours > 72:  # 3+ days
            return ("alternative_recommendation", f"Lead compared projects {hours:.0f}h ago. Suggest alternatives.")
        return ("visit_prompt", f"Lead in {stage} with project interest. Encourage visit.")

    # Hot/warm lead + long silence -> value-based
    if score >= 55 and hours > 48:
        return ("value_based_follow_up", f"Score {score}, silent {hours:.0f}h. Share value/insight.")

    # Default: gentle reminder
    return ("gentle_reminder", f"Stage {stage}, score {score}, {hours:.0f}h since last. Gentle nudge.")


def _generate_message(
    follow_up_type: str,
    *,
    last_projects: list,
    buyer_stage: str,
    lang: str = "ar",
) -> tuple[str, str]:
    """Generate short, natural message. Returns (ar, en)."""
    projects = last_projects or []
    proj_names = ", ".join(projects[:2]) if projects else "المشاريع التي ناقشناها"

    messages = {
        "gentle_reminder": (
            "أهلاً! تذكرتك ووديت أطمن إننا موجودين لمساعدتك. لو حابب نكمل حديثنا أو عندك أي سؤال، أنا هنا.",
            "Hi! Just wanted to check in—we're here when you need us. If you'd like to continue our conversation or have any questions, I'm here.",
        ),
        "alternative_recommendation": (
            f"مرحباً! بما إنك كنت مهتماً بـ {proj_names}، عندنا خيارات مشابهة قد تناسبك. تحب أرسل لك التفاصيل؟",
            f"Hi! Since you were interested in {proj_names}, we have similar options that might fit. Would you like me to send the details?",
        ) if projects else (
            "مرحباً! عندنا عروض جديدة قد تهمك. تحب نشاركك بها؟",
            "Hi! We have new offers that might interest you. Would you like us to share them?",
        ),
        "visit_prompt": (
            "أهلاً! زيارة سريعة للموقع هتساعدك تتخذ قرار أوضح. متى يناسبك نرتب المعاينة؟",
            "Hi! A quick site visit will help you decide with clarity. When would work for you to schedule a viewing?",
        ),
        "value_based_follow_up": (
            "مرحباً! عايز نشاركك ببعض التحديثات عن السوق والمشاريع اللي قد تناسبك. متاح لو تحب نتواصل.",
            "Hi! We'd like to share some market updates and projects that might suit you. Let me know if you'd like to connect.",
        ),
    }
    ar, en = messages.get(follow_up_type, messages["gentle_reminder"])
    return (ar, en)


def _compute_priority(
    follow_up_type: str,
    lead_score: int,
    time_since_last_hours: float,
) -> int:
    """Higher = more urgent. Range 0-100."""
    base = 50
    if follow_up_type == "visit_prompt":
        base = 75
    elif follow_up_type == "alternative_recommendation":
        base = 65
    elif follow_up_type == "value_based_follow_up":
        base = 60
    # Boost for hot leads
    if lead_score >= 70:
        base = min(95, base + 15)
    elif lead_score >= 55:
        base = min(90, base + 10)
    # Slight boost for long silence (don't over-prioritize)
    if time_since_last_hours > 96:  # 4+ days
        base = min(95, base + 5)
    return min(100, max(0, base))


def generate_follow_up_recommendations(
    *,
    buyer_stage: str = "",
    lead_score: int = 0,
    last_discussed_projects: list[str] | None = None,
    time_since_last_interaction_hours: float = 0.0,
    lead_ref: str = "",
    lang: str = "ar",
) -> list[FollowUpRecommendation]:
    """
    Generate structured follow-up recommendations for a dormant lead.
    Returns list of FollowUpRecommendation (stored as records). Does NOT send.
    """
    projects = list(last_discussed_projects or [])
    follow_up_type, reasoning = _select_follow_up_type(
        buyer_stage=buyer_stage,
        lead_score=lead_score,
        last_projects=projects,
        time_since_last_hours=time_since_last_interaction_hours,
    )
    msg_ar, msg_en = _generate_message(
        follow_up_type,
        last_projects=projects,
        buyer_stage=buyer_stage,
        lang=lang,
    )
    priority = _compute_priority(
        follow_up_type,
        lead_score,
        time_since_last_interaction_hours,
    )
    rec = FollowUpRecommendation(
        type=follow_up_type,
        message_text=msg_ar,
        message_text_en=msg_en,
        reasoning=reasoning,
        priority=priority,
        lead_ref=lead_ref,
        time_since_last_hours=time_since_last_interaction_hours,
        buyer_stage=buyer_stage,
        lead_score=lead_score,
        last_projects=projects,
    )
    return [rec]
