"""
Objection-handling library - Egyptian real estate.
Arabic + English. Never overpromise; distinguish verified vs general.
Handles Egyptian, Gulf, typo-heavy, and mixed Arabic/English.
"""
from dataclasses import dataclass
from typing import Optional

from engines.arabic_normalizer import normalize_for_detection


@dataclass
class ObjectionResponse:
    """Structured objection response."""
    key: str
    response_ar: str
    response_en: str
    follow_up_question_ar: str = ""
    follow_up_question_en: str = ""


# Objection library: key -> (AR, EN responses)
# Natural consultant tone; varied follow-ups to avoid repetition
OBJECTIONS: dict[str, ObjectionResponse] = {
    "price_too_high": ObjectionResponse(
        key="price_too_high",
        response_ar="فهمت تماماً—السعر هام لأي قرار. أسعارنا تعكس جودة البناء والموقع. عندنا خطط تقسيط مرنة ومشاريع في نطاقات مختلفة. لو توضح نطاق ميزانيتك أقدر أرشح لك الأنسب.",
        response_en="I understand—price matters for any decision. Our pricing reflects build quality and location. We have flexible payment plans and projects at different price points. If you share your budget range, I can recommend the best fit.",
        follow_up_question_ar="هل تفضل الدفع كاش أو تقسيط؟ وكام مقدم مريح ليك؟",
        follow_up_question_en="Do you prefer cash or installments? And what down payment works for you?",
    ),
    "location_concern": ObjectionResponse(
        key="location_concern",
        response_ar="الموقع فعلاً أساسي—كل منطقة ليها مميزاتها. عندنا مشاريع في المعادي والتجمع وأكتوبر والشيخ زايد والشروق. لو تحدد أولوياتك (قرب من العمل، مدارس، هدوء) أرشح لك الأنسب.",
        response_en="Location is key—each area has its strengths. We have projects in Maadi, New Cairo, October, Sheikh Zayed, and Shorouk. If you share your priorities—near work, schools, quiet—I'll recommend the best fit.",
        follow_up_question_ar="إيه الأهم عندك؟ القرب من الشغل ولا الهدوء والخدمات؟",
        follow_up_question_en="What matters most—proximity to work or peace and amenities?",
    ),
    "trust_credibility": ObjectionResponse(
        key="trust_credibility",
        response_ar="نفهم أهمية الثقة. نحن شركة راسخة ولنا سجل تسليمات. يمكننا ترتيب زيارة للموقع أو مشاركة دراسات الحالة والتسليمات السابقة. هل تود الاطلاع على تجارب عملاء سابقين؟",
        response_en="We understand the importance of trust. We're an established company with a strong delivery track record. We can arrange a site visit or share case studies. Would you like to see testimonials from previous customers?",
        follow_up_question_ar="هل تفضل جولة ميدانية أم مواد توضيحية أولاً؟",
        follow_up_question_en="Would you prefer a site tour or materials first?",
    ),
    "payment_plan_mismatch": ObjectionResponse(
        key="payment_plan_mismatch",
        response_ar="نقدم خطط تقسيط متنوعة حسب المشروع. بعضها مقدم أقل ونسبة أعلى على التسليم، وآخرون العكس. أخبرني بالقسط الشهري المريح لك، ونقترح الأنسب.",
        response_en="We offer flexible payment plans per project. Some have lower down payment and higher on delivery; others the opposite. Tell me your comfortable monthly installment, and we'll suggest the best fit.",
        follow_up_question_ar="ما أقصى مقدم يمكنك دفعه؟",
        follow_up_question_en="What's the maximum down payment you can make?",
    ),
    "investment_uncertainty": ObjectionResponse(
        key="investment_uncertainty",
        response_ar="الاستثمار العقاري يحتاج دراسة. نساعدك بمعلومات عن مناطق النمو والتأجير. الأسعار والتفاصيل الدقيقة نقدمها بعد تحديد المشروع المناسب. هل تفضل الاستثمار السكني أم التجاري؟",
        response_en="Real estate investment needs careful study. We provide information on growth areas and rental potential. Exact figures come after we narrow down the right project. Do you prefer residential or commercial investment?",
        follow_up_question_ar="ما فترة الاستثمار المتوقعة؟",
        follow_up_question_en="What's your expected investment horizon?",
    ),
    "waiting_hesitation": ObjectionResponse(
        key="waiting_hesitation",
        response_ar="أخذ وقتك قرار سليم—القرار العقاري مهم. نرسل لك مواد للمراجعة ومعاينة لما تكون جاهز، بدون أي ضغط. تحب نتواصل إمتى؟",
        response_en="Taking your time makes sense—it's a big decision. We'll send materials to review and arrange a visit when you're ready, no pressure. When would you like to reconnect?",
        follow_up_question_ar="تحب أبعث لك بروشورات عشان تقارن في راحتك؟",
        follow_up_question_en="Would you like me to send brochures so you can compare at your pace?",
    ),
    "comparing_projects": ObjectionResponse(
        key="comparing_projects",
        response_ar="مقارنة المشاريع خطوة سليمة. نستطيع توضيح الفروقات الرئيسية—الموقع، السعر، والتسليم. أي مشروعين تقارن؟",
        response_en="Comparing projects is smart. We can highlight key differences—location, price, and delivery. Which two are you comparing?",
        follow_up_question_ar="هل تود زيارة ميدانية للمقارنة؟",
        follow_up_question_en="Would a site visit help you compare?",
    ),
    "delivery_concerns": ObjectionResponse(
        key="delivery_concerns",
        response_ar="التسليم يختلف حسب المشروع والمرحلة. نشارك ما نعرفه وننصح بالتأكيد مع فريق المبيعات. هل تود معرفة المراحل والتواريخ المتوقعة؟",
        response_en="Delivery varies by project and phase. We share what we know and recommend confirming with sales. Would you like expected phases and dates?",
        follow_up_question_ar="هل نرتب لك زيارة لمعاينة المراحل؟",
        follow_up_question_en="Shall we arrange a visit to see the phases?",
    ),
}


def detect_objection(text: str) -> Optional[str]:
    """Detect objection type from user message. Uses normalized text for Egyptian/Gulf/typos."""
    t = normalize_for_detection(text or "")
    # Expand patterns: Egyptian, Gulf, typos, mixed
    patterns = {
        "price_too_high": [
            "غالي", "غالية", "expensive", "مكلف", "مكلفة", "ميزانيتي أقل", "ميزانتي اقل",
            "over budget", "أرخص", "cheaper", "غاليه", "غلَي", "غاليا عليا", "غالي جداً",
            "ميزانيتي مش كفاية", "السعر مرتفع", "الاسعار عالية", "too expensive",
        ],
        "location_concern": [
            "الموقع", "مكان بعيد", "location", "بعيد عن", "far from", "أين بالتحديد",
            "المنطقة مش مناسبة", "مش متأكد من المنطقة", "الموقع بعيد", "وين بالضبط",
        ],
        "trust_credibility": [
            "مش واثق", "ما واثق", "trust", "credibility", "ضامن", "guarantee",
            "شركة معروفة", "سجل", "track record", "مين تضمن",
        ],
        "payment_plan_mismatch": [
            "التقسيط", "المقدم", "القسط", "installment", "down payment", "مش مقتدر",
            "المقدم كتير", "القسط عالي", "مقدم اقل", "تمويل",
        ],
        "investment_uncertainty": [
            "استثمار", "investment", "شك", "مش متأكد", "uncertain", "عائد", "return",
            "لست متأكد", "مش عارف", "العائد مضمون",
        ],
        "waiting_hesitation": [
            "أستني", "استنى", "أمهلني", "wait", "لاحقاً", "later", "فكر", "think about it",
            "مش مستعجل", "ليس مستعجل", "هستنى", "سأنتظر", "أخذ وقت", "دلوقتي لا", "not now",
        ],
        "comparing_projects": [
            "بين مشروعين", "مقارنة", "comparing", "أيهما أفضل", "الفرق بين", "أقارن",
            "مقارنه", "افضل مشروع", "الفرق شنو", "ويش الفرق",
        ],
        "delivery_concerns": [
            "التسليم", "delivery", "متى التسليم", "مخاوف التسليم", "يتأخر",
            "التأخير", "متى الاستلام", "متى يسلم",
        ],
    }
    for key, words in patterns.items():
        if any(w in t for w in words):
            return key
    return None


def get_objection_response(key: str, lang: str = "ar") -> str:
    """Get objection response in requested language."""
    obj = OBJECTIONS.get(key)
    if not obj:
        return ""
    return obj.response_ar if lang in ("ar", "arabic") else obj.response_en


def get_follow_up(key: str, lang: str = "ar") -> str:
    """Get follow-up question for objection."""
    obj = OBJECTIONS.get(key)
    if not obj:
        return ""
    return obj.follow_up_question_ar if lang in ("ar", "arabic") else obj.follow_up_question_en
