"""
Persuasion and Objection Handling - ethical, consultant-style responses.
Value framing, tradeoff explanation, social proof (when grounded), scarcity only when true.
Avoids pressure and false urgency.
"""
from dataclasses import dataclass, field
from typing import Optional

# Objection types we support
OBJECTION_TYPES = frozenset({
    "price_too_high",
    "unsure_about_area",
    "comparing_projects",
    "wants_more_time",
    "investment_value_concern",
    "delivery_concerns",
    "financing_concerns",
    "trust_credibility",
})


@dataclass
class PersuasionOutput:
    """Ethical persuasion result for an objection."""
    objection_type: str
    handling_strategy: str
    persuasive_points: list[str] = field(default_factory=list)
    preferred_cta: str = "address_objection"


# Handling strategies - consultant-style, no pressure
HANDLING_STRATEGIES: dict[str, str] = {
    "price_too_high": "value_framing_plus_options",
    "unsure_about_area": "tradeoff_explanation",
    "comparing_projects": "comparison_support",
    "wants_more_time": "next_step_encouragement",
    "investment_value_concern": "value_framing",
    "delivery_concerns": "tradeoff_explanation",
    "financing_concerns": "options_explanation",
    "trust_credibility": "social_proof_when_grounded",
}

# Persuasive points - ethical only. No false urgency.
PERSUASIVE_POINTS: dict[str, list[str]] = {
    "price_too_high": [
        "Quality and location justify the price—focus on what you get.",
        "Flexible payment plans can spread the cost.",
        "We can show options in different price bands.",
    ],
    "unsure_about_area": [
        "Different areas suit different needs—we can narrow by your priorities.",
        "A site visit often clarifies—seeing the project helps decide.",
        "Many clients compare two areas before deciding.",
    ],
    "comparing_projects": [
        "Comparing is wise—we can highlight key differences.",
        "Each project has pros and cons—we help you weigh them.",
        "A comparison visit can make the choice clearer.",
    ],
    "wants_more_time": [
        "Taking your time is fine—we're here when you're ready.",
        "A quick site visit can help without commitment.",
        "We can send materials so you can review at your pace.",
    ],
    "investment_value_concern": [
        "We share area data and trends—no guarantees, just facts.",
        "Long-term hold often smoothes short-term volatility.",
        "We can discuss different areas and their track records.",
    ],
    "delivery_concerns": [
        "Delivery schedules vary—we share what we know and recommend confirmation.",
        "Phased delivery is common—earlier phases often deliver sooner.",
        "Our team can clarify expected timelines for specific units.",
    ],
    "financing_concerns": [
        "Multiple payment plans exist—we find what fits your situation.",
        "Lower down payment options are available on some projects.",
        "Our team can walk you through the numbers clearly.",
    ],
    "trust_credibility": [
        "We share our track record when you're ready—no pressure.",
        "Site visits and materials help you verify for yourself.",
        "Our team is available to answer specific questions.",
    ],
}

# Arabic persuasive points - natural consultant tone
PERSUASIVE_POINTS_AR: dict[str, list[str]] = {
    "price_too_high": [
        "الجودة والموقع يبرران السعر—ركز على اللي هتحصل عليه.",
        "خطط التقسيط المرنة تقسم التكلفة على وقت أطول.",
        "نقدر نوريك خيارات في نطاقات أسعار مختلفة.",
    ],
    "unsure_about_area": [
        "كل منطقة ليها مميزاتها—نقدر نضيق بحسب أولوياتك.",
        "زيارة الموقع غالباً توضح الصورة.",
        "كثير من العملاء يقارنوا منطقتين قبل القرار.",
    ],
    "comparing_projects": [
        "المقارنة خطوة ذكية—نقدر نوضح الفروقات الأساسية.",
        "كل مشروع له إيجابيات وسلبيات—نساعدك توزن.",
        "زيارة مقارنة توضح الاختيار.",
    ],
    "wants_more_time": [
        "أخذ وقتك طبيعي—نحن هنا لما تكون جاهز.",
        "معاينة سريعة تساعد بدون التزام.",
        "نبعث مواد تراجعها في راحتك.",
    ],
    "investment_value_concern": [
        "نشارك بيانات المناطق والاتجاهات—بدون وعود، حقائق فقط.",
        "الاحتفاظ طويل المدى غالباً يلين التقلبات.",
        "نناقش مناطق مختلفة وسجلاتها.",
    ],
    "delivery_concerns": [
        "التسليم يختلف—نشارك اللي نعرفه وننصح بالتأكيد مع المبيعات.",
        "التسليم المرحلي شائع—المراحل الأولى غالباً أسرع.",
        "فريقنا يوضح المواعيد المتوقعة للوحدات.",
    ],
    "financing_concerns": [
        "خطط دفع متعددة—نجد اللي يناسب وضعك.",
        "مقدم أقل متاح في بعض المشاريع.",
        "فريقنا يشرح الأرقام بوضوح.",
    ],
    "trust_credibility": [
        "نشارك سجلنا لما تكون جاهز—بدون ضغط.",
        "زيارات الموقع والمواد تساعدك تتأكد بنفسك.",
        "فريقنا جاهز لأي استفسار محدد.",
    ],
}


def get_persuasive_points(objection_type: str, lang: str = "en") -> list[str]:
    """Get persuasive points in requested language."""
    points = PERSUASIVE_POINTS_AR if lang in ("ar", "arabic") else PERSUASIVE_POINTS
    return points.get(objection_type, []) or PERSUASIVE_POINTS.get("price_too_high", [])


# Preferred CTA per objection - next-step encouragement, not pressure
PREFERRED_CTAS: dict[str, str] = {
    "price_too_high": "ask_budget",
    "unsure_about_area": "ask_location",
    "comparing_projects": "recommend_projects",
    "wants_more_time": "nurture",
    "investment_value_concern": "recommend_projects",
    "delivery_concerns": "propose_visit",
    "financing_concerns": "recommend_projects",
    "trust_credibility": "propose_visit",
}

# Arabic detection patterns - Egyptian, Gulf, typos, mixed
OBJECTION_PATTERNS: dict[str, list[str]] = {
    "price_too_high": [
        "غالي", "غالية", "غاليه", "غاليا عليا", "expensive", "مكلف", "مكلفة",
        "ميزانيتي أقل", "ميزانتي اقل", "over budget", "أرخص", "cheaper",
        "السعر مرتفع", "الأسعار عالية", "too expensive",
    ],
    "unsure_about_area": [
        "الموقع", "مكان بعيد", "location", "بعيد عن", "far from",
        "غير متأكد من المنطقة", "مش عارف المنطقة", "أين بالتحديد",
        "unsure about area", "مش متأكد من المنطقة", "الموقع بعيد", "وين بالضبط",
    ],
    "comparing_projects": [
        "بين مشروعين", "مقارنة", "مقارنه", "comparing", "أيهما أفضل",
        "الفرق بين", "difference between", "أقارن", "افضل مشروع",
    ],
    "wants_more_time": [
        "أستني", "استنى", "أمهلني", "wait", "لاحقاً", "later", "فكر",
        "think about it", "مش مستعجل", "ليس مستعجل", "هستنى", "I'll think", "أخذ وقت",
        "سأنتظر", "دلوقتي لا", "not now",
    ],
    "investment_value_concern": [
        "استثمار", "investment", "شك", "مش متأكد", "uncertain",
        "عائد", "return", "قيمة الاستثمار", "investment value",
        "مش متأكد من العائد", "worried about value", "لست متأكد",
    ],
    "delivery_concerns": [
        "التسليم", "delivery", "متى التسليم", "when delivery",
        "مخاوف التسليم", "delivery concerns", "يتأخر", "متى الاستلام",
        "متى يسلم",
    ],
    "financing_concerns": [
        "التقسيط", "المقدم", "القسط", "installment", "down payment",
        "مش مقتدر", "financing", "تمويل", "الدفع", "المقدم كتير",
    ],
    "trust_credibility": [
        "مش واثق", "ما واثق", "trust", "credibility", "ضامن", "guarantee",
        "شركة معروفة", "سجل", "track record", "مين تضمن",
    ],
}


def detect_objection_type(text: str) -> Optional[str]:
    """Detect objection type from user message. Uses normalized text for Arabic variants."""
    from engines.arabic_normalizer import normalize_for_detection
    t = normalize_for_detection(text or "")
    for key, patterns in OBJECTION_PATTERNS.items():
        if any(p.lower() in t for p in patterns):
            return key
    return None


def get_persuasion_output(objection_type: str) -> PersuasionOutput:
    """Get ethical persuasion output for an objection type."""
    if objection_type not in OBJECTION_TYPES:
        return PersuasionOutput(
            objection_type=objection_type,
            handling_strategy="empathy_first",
            persuasive_points=["We understand. How can we help?"],
            preferred_cta="address_objection",
        )
    return PersuasionOutput(
        objection_type=objection_type,
        handling_strategy=HANDLING_STRATEGIES.get(objection_type, "empathy_first"),
        persuasive_points=PERSUASIVE_POINTS.get(objection_type, []),
        preferred_cta=PREFERRED_CTAS.get(objection_type, "address_objection"),
    )


def map_legacy_objection_to_type(legacy_key: str) -> str:
    """Map objection_library keys to persuasion objection types."""
    mapping = {
        "price_too_high": "price_too_high",
        "location_concern": "unsure_about_area",
        "payment_plan_mismatch": "financing_concerns",
        "investment_uncertainty": "investment_value_concern",
        "waiting_hesitation": "wants_more_time",
        "trust_credibility": "trust_credibility",
        "comparing_projects": "comparing_projects",
        "delivery_concerns": "delivery_concerns",
    }
    return mapping.get(legacy_key, legacy_key)
