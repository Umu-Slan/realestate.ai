"""
Build recommendation response text from ProjectMatch list.
Never fabricate. Clearly mark verified vs general. Safe language for unverified facts.
"""
from typing import Optional

from engines.recommendation_engine import ProjectMatch


def build_recommendation_response(
    matches: list[ProjectMatch],
    *,
    lang: str = "ar",
    qualification_summary: str = "",
) -> str:
    """
    Turn matches into professional recommendation text.
    Adds safety disclaimer when pricing is unverified.
    """
    if not matches:
        if lang == "ar":
            return "حالياً لا توجد توصيات مطابقة في قاعدة البيانات. فريقنا يمكنه اقتراح بدائل—هل تود التواصل مع استشاري؟"
        return "We don't have direct matches in our database right now. Our team can suggest alternatives—would you like to speak with an advisor?"

    lines = []
    if lang == "ar":
        q = f" ({qualification_summary})" if qualification_summary else ""
        lines.append(f"بناءً على معاييرك{q}، إليك أفضل الخيارات المناسبة:\n")
    else:
        q = f" ({qualification_summary})" if qualification_summary else ""
        lines.append(f"Based on your criteria{q}, here are the best matching options:\n")

    for i, m in enumerate(matches, 1):
        name = m.project_name_ar or m.project_name
        if lang == "en":
            name = m.project_name
        line = f"\n{i}. **{name}**"
        if m.location:
            line += f" — {m.location}"
        if m.price_min and m.price_max:
            pmin, pmax = float(m.price_min), float(m.price_max)
            if lang == "ar":
                # Arabic-friendly: "3,000,000 جنيه" format
                line += f" — نطاق أسعار تقريبي: {pmin:,.0f}–{pmax:,.0f} جنيه"
                if not m.has_verified_pricing:
                    line += " (يرجى التأكد من فريق المبيعات)"
            else:
                line += f" — Approx. price range: {pmin:,.0f}–{pmax:,.0f} EGP"
                if not m.has_verified_pricing:
                    line += " (confirm with sales)"
        elif m.price_min or m.price_max:
            p = float(m.price_min or m.price_max or 0)
            if lang == "ar":
                line += f" — من {p:,.0f} جنيه"
            else:
                line += f" — From {p:,.0f} EGP"
        if m.rationale:
            # Natural Arabic: avoid robotic "rationale: X"
            line += f". {m.rationale}"
        if m.trade_offs:
            trade_txt = ", ".join(m.trade_offs[:2])
            if lang == "ar":
                line += f" (ملاحظة: {trade_txt})"
            else:
                line += f" (note: {trade_txt})"
        lines.append(line)

    if lang == "ar":
        lines.append("\nللأسعار الدقيقة والتوفر الحالي، يرجى التواصل مع فريق المبيعات.")
    else:
        lines.append("\nFor exact prices and current availability, please contact our sales team.")

    return "".join(lines)
