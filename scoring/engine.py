"""
Deterministic lead scoring engine. Rules-based, explainable.
"""
from dataclasses import dataclass

from leads.models import LeadQualification
from leads.models import Customer


@dataclass
class ScoreResult:
    score: int
    tier: str
    explanation: list[dict]


def score_lead(customer: Customer, qualification: LeadQualification | None = None) -> ScoreResult:
    """
    Compute lead score using deterministic rules.
    Returns score (0-100), tier (hot/warm/cold), and explanation.
    """
    explanations = []
    points = 0

    if qualification:
        # Budget indicated
        if qualification.budget_min or qualification.budget_max:
            points += 20
            explanations.append({"factor": "budget_indicated", "contribution": 20})

        # Property type specified
        if qualification.property_type:
            points += 15
            explanations.append({"factor": "property_type", "contribution": 15})

        # Location preference
        if qualification.location_preference:
            points += 15
            explanations.append({"factor": "location", "contribution": 15})

        # Timeline (buying soon)
        if qualification.timeline:
            timeline_lower = qualification.timeline.lower()
            if any(x in timeline_lower for x in ["شهر", "شهور", "أسبوع", "قريب", "فوراً", "now", "soon", "month"]):
                points += 25
                explanations.append({"factor": "near_term_timeline", "contribution": 25})
            else:
                points += 5
                explanations.append({"factor": "timeline", "contribution": 5})

    # Default: cold if no qualification
    if not qualification or points == 0:
        explanations.append({"factor": "no_qualification", "contribution": 0})

    points = min(100, points)

    if points >= 60:
        tier = "hot"
    elif points >= 30:
        tier = "warm"
    else:
        tier = "cold"

    return ScoreResult(score=points, tier=tier, explanation=explanations)
