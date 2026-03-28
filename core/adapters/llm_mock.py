"""
Mock LLM for DEMO_MODE — context-aware sales-style replies without API calls.

Reads the same `messages` list the real LLM gets (system + history + user) so
multi-turn chat stays coherent. For production quality, set DEMO_MODE=false and
OPENAI_API_KEY (no fine-tuning required unless you choose it later).
"""
from __future__ import annotations

import re
from typing import Optional

from core.adapters.llm import BaseLLMClient


def _detect_lang(text: str) -> str:
    if re.search(r"[\u0600-\u06FF]", text or ""):
        return "ar"
    return "en"


def _parse_sales_context(system_blob: str) -> dict[str, Optional[str]]:
    """Extract hints from sales_engine system block (Budget:, Location:, etc.)."""
    ctx: dict[str, Optional[str]] = {
        "budget": None,
        "location": None,
        "property_type": None,
        "project": None,
    }
    if not system_blob:
        return ctx
    for line in system_blob.splitlines():
        line = line.strip()
        if line.startswith("Budget:"):
            ctx["budget"] = line.replace("Budget:", "").strip()
        elif line.startswith("Location:"):
            ctx["location"] = line.replace("Location:", "").strip()
        elif line.startswith("Property type:"):
            ctx["property_type"] = line.replace("Property type:", "").strip()
        elif line.startswith("Project interest:"):
            ctx["project"] = line.replace("Project interest:", "").strip()
    return ctx


def _count_turns(messages: list[dict]) -> int:
    n = 0
    for m in messages:
        if m.get("role") == "assistant":
            n += 1
    return n


def _join_system(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        if m.get("role") == "system":
            parts.append((m.get("content") or "").strip())
    return "\n".join(parts)


def _last_user(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def _channel_from_system(system_blob: str) -> str:
    m = re.search(r"CHANNEL:\s*(\w+)", system_blob or "", re.IGNORECASE)
    return (m.group(1) if m else "web").lower()


def _looks_like_scheduling_message(text: str, lang: str) -> bool:
    """
    True when the user is proposing or confirming a visit time window (not only saying 'visit').
    Keeps mock replies from re-stating budget when the last turn is scheduling.
    """
    raw = text or ""
    low = raw.lower()
    if lang == "ar":
        markers = (
            "زيارة",
            "معاينة",
            "موعد",
            "حجز",
            "يناسبني",
            "يناسبنى",
            "الساعة",
            "صباحاً",
            "صباحا",
            "عصراً",
            "عصرا",
            "مساءً",
            "مساء",
            "ظهراً",
            "ظهرا",
            "الاثنين",
            "الثلاثاء",
            "الأربعاء",
            "الخميس",
            "الجمعة",
            "السبت",
            "الأحد",
            "اثنين",
            "ثلاثاء",
            "أربعاء",
            "خميس",
            "جمعة",
            "سبت",
            "أحد",
            "العاشرة",
            "الرابعة",
            "الثالثة",
            "الواحدة",
            "غداً",
            "غدا",
            "القادم",
        )
        return any(m in raw for m in markers)
    return bool(
        re.search(
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"am\b|pm\b|a\.m\.?|p\.m\.?|morning|afternoon|evening|noon|"
            r"schedule|slot|works for me|book a)\b",
            low,
        )
    )


def _trim_for_channel(text: str, system_blob: str) -> str:
    """Keep demo replies within typical limits for SMS/WhatsApp."""
    if not text:
        return text
    ch = _channel_from_system(system_blob)
    if ch == "sms" and len(text) > 300:
        cut = text[:297]
        if "." in cut:
            return cut.rsplit(".", 1)[0] + "."
        return cut + "…"
    if ch == "whatsapp" and len(text) > 850:
        cut = text[:820]
        if "\n\n" in cut:
            blocks = cut.split("\n\n")
            return "\n\n".join(blocks[:-1]) if len(blocks) > 1 else cut + "…"
        if "." in cut:
            return cut.rsplit(".", 1)[0] + "."
        return cut + "…"
    return text


class MockLLMClient(BaseLLMClient):
    """Sales-closer style canned logic that respects conversation context."""

    def chat_completion(self, messages: list[dict], **kwargs) -> str:
        if not messages:
            return "مرحباً! كيف يمكنني مساعدتك اليوم؟"

        system_blob = _join_system(messages)
        last = _last_user(messages)
        lang = _detect_lang(last) if last else _detect_lang(system_blob)
        turns = _count_turns(messages)
        ctx = _parse_sales_context(system_blob)
        t = (last or "").lower()

        # Support path (distinct system prompt — avoid false positives from sales text)
        if "You are a support representative" in system_blob:
            return _trim_for_channel(self._support_reply(last, lang), system_blob)

        return _trim_for_channel(self._sales_reply(last, lang, ctx, turns, t), system_blob)

    def _support_reply(self, last: str, lang: str) -> str:
        t = (last or "").lower()
        if lang == "ar":
            if "موظف" in t or "human" in t or "agent" in t:
                return (
                    "تمام — هنسجّل طلب التواصل مع ممثل مبيعات خلال أقرب وقت عمل. "
                    "ممكن تكتب رقمك أو أفضل وقت للاتصال؟"
                )
            if "تسليم" in t or "delivery" in t:
                return (
                    "بالنسبة لمواعيد التسليم: بنأكد المرحلة حسب المشروع والعقد. "
                    "تحب أرشّح لك مشروع بمرحلة تسليم تناسبك، ولا تفضّل تتكلم مع فريق المبيعات مباشرة؟"
                )
            return (
                "شكراً لتواصلك. عشان أساعدك بدقة: اذكر نوع الاستفسار (تقسيط، تسليم، صيانة، عقد) "
                "وهرجع لك بخطوة واضحة."
            )
        if "agent" in t or "human" in t:
            return (
                "Got it — I'll flag this for a sales rep. Please share your phone or best time to call."
            )
        return (
            "Thanks for reaching out. Tell me whether this is about payment plan, delivery, "
            "or paperwork so I can give the exact next step."
        )

    def _sales_reply(
        self,
        last: str,
        lang: str,
        ctx: dict[str, Optional[str]],
        turns: int,
        t: str,
    ) -> str:
        b = ctx.get("budget")
        loc = ctx.get("location")
        pt = ctx.get("property_type")
        proj = ctx.get("project")

        if lang == "ar":
            return self._sales_reply_ar(last, b, loc, pt, proj, turns, t)
        return self._sales_reply_en(last, b, loc, pt, proj, turns, t)

    def _sales_reply_ar(
        self,
        last: str,
        b: Optional[str],
        loc: Optional[str],
        pt: Optional[str],
        proj: Optional[str],
        turns: int,
        t: str,
    ) -> str:
        # Objections / friction
        if any(x in t for x in ("غالي", "عالي", "expensive", "too much", "مش هقدر")):
            return (
                "فاهم قلقك من السعر — غالباً فيه خطط دفع وأنظمة تقسيط تخفّض العبء الشهري. "
                "نقدر نرشّح وحدات ضمن نطاق أقرب لميزانيتك. تحب نحدد **حد أقصى شهري مريح** عشان أضيق الخيارات؟"
            )
        if any(x in t for x in ("مش متأكد", "محتار", "مش عارف", "later", "بعدين")):
            return (
                "طبيعي جداً تكون محتار — نقدر نمشي خطوة خطوة بدون ضغط. "
                "لو تحب: نبدأ بسؤال واحد — **الشراء للسكن ولا للاستثمار؟** وبناءً عليه أشرح لك أنسب نمط مشروع."
            )
        if _looks_like_scheduling_message(last, "ar"):
            loc_echo = f" تم تأكيد تفضيلك لـ **{loc}**." if loc else ""
            pt_echo = f"نوع الوحدة: **{pt}**." if pt else ""
            return (
                "تمام — استلمت **الفترة الزمنية** اللي ذكرتها للمعاينة."
                + loc_echo
                + (f" {pt_echo}" if pt_echo else "")
                + " خطوتنا التالية: فريق المبيعات يكمل معاك ل**تثبيت الموعد** واقتراح أقرب مشروع مناسب. "
                "لو تحب اذكر **أفضل رقم تواصل** أو أي ملاحظة للمندوب."
            )
        if any(x in t for x in ("زيارة", "معاينة", "visit", "موعد")):
            return (
                "ممتاز — المعاينة غالباً هي خطوة القرار الأوضح. "
                "قولّي **أيام الأسبوع** اللي تناسبك (صباح/مساء) وهل تفضّل **الشيخ زايد، التجمع، أو منطقة تانية** عشان نرتب لك مقترح مواعيد."
            )
        if any(x in t for x in ("تقسيط", "مقدم", "قسط", "installment")):
            return (
                "تمام — خطط التقسيط تختلف حسب المشروع ومرحلة التسليم. "
                "عشان ما أقولش رقم غير دقيق: **تفضّل دفعة مقدمة تقريبية كام وحد أقصى قسط شهري؟** وأنا أربطك بأقرب خيارات منطقية."
            )

        # Rich context from qualification
        if b and loc:
            extra = f" النوع: {pt}." if pt else ""
            pr = f" اهتمامك بمشروع **{proj}** مسجّل." if proj else ""
            if turns >= 2:
                return (
                    f"بناءً على كلامك: الميزانية ضمن نطاق **{b}** والمنطقة **{loc}**.{extra}{pr} "
                    "الخطوة الجاية المنطقية: أرشّح لك ٢–٣ خيارات متوافقة، وبعدها نثبت **معاينة** لو تحب. "
                    "تحب نبدأ بأقرب مشروع للتسليم السريع ولا الأفضل سعر/مساحة؟"
                )
            return (
                f"جميل — واضح إن نطاق **{b}** ومنطقة **{loc}** شكلهم مناسبين لبحثك.{extra} "
                "عشان أرشّح بدقة: **تفضّل تسليم خلال كام سنة تقريباً؟** وهل أولويتك المساحة ولا الموقع؟"
            )

        if b and not loc:
            return (
                f"تمام، نطاق الميزانية **{b}** واضح — ده يساعدني أضيق الخيارات. "
                "**أي مناطق تفضّلها؟** (مثلاً: الشيخ زايد، التجمع، أكتوبر، أو القاهرة الجديدة)"
            )

        if loc and not b:
            return (
                f"ممتاز — **{loc}** منطقة قوية وفيها أكتر من مشروع. "
                "عشان ما أعرضش حاجة خارج النطاق: **ما هو نطاق الميزانية التقريبي** (من — إلى) بالجنيه؟"
            )

        if any(x in t for x in ("شقة", "فيلا", "دوبلكس", "apartment", "villa")):
            return (
                "تمام — عشان أرشّح وحدات مناسبة: **كم غرفة نوم تقريباً؟** "
                "و**الميزانية التقريبية** و**المنطقة المفضّلة**؟ (كل ما كانت الإجابات أوضح، الترشيح أدق.)"
            )

        if any(x in t for x in ("سعر", "price", "كم", "بكام")):
            return (
                "الأسعار الدقيقة بتختلف حسب الوحدة والدور والمرحلة. "
                "أقدر أعطيك **نطاقاً تقريبياً** بعد ما أعرف: **الميزانية** و**المنطقة** و**نوع الوحدة**. "
                "تقدر تكتبهم في سطر واحد؟"
            )

        if any(x in t for x in ("استثمار", "invest")):
            return (
                "حلو — لو الهدف استثمار: بنركّز على **العائد، السيولة، ومرحلة التسليم**. "
                "تحب **أفق ٣ سنوات** ولا **٥–٧ سنوات**؟ وما **نطاق الميزانية** اللي مريح لك؟"
            )

        if any(
            x in (last or "")
            for x in (
                "رشحلي",
                "رشّحلي",
                "ارشحلي",
                "رشحني",
                "رشح لي",
                "ارشح لي",
                "اقترحلي",
                "اقترح لي",
                "وصّيني",
                "وصيني",
                "عرض المشاريع",
                "مشاريع مناسبة",
                "مشاريع مقترحة",
            )
        ) or any(
            x in t
            for x in (
                "recommend",
                "suggest project",
                "show projects",
            )
        ):
            return (
                "تمام — هنشتغل على **ترشيح** يناسبك. عشان أطلع لك خيارات واقعية ومش عشوائية: "
                "محتاج **الميزانية التقريبية** و**المنطقة** (زي الشيخ زايد أو التجمع أو أكتوبر). "
                "ولو تحب زوّد **شقة ولا فيلا** و**للسكن ولا للاستثمار**."
            )

        # Early turn openers (varied by turn count)
        openers = [
            (
                "أهلاً بيك — أنا معاك خطوة بخطوة لحد ما نوصل لأنسب خيار. "
                "عشان أبدأ بترشيح ذكي: **إيه الميزانية التقريبية** و**أي منطقة** في بالك؟"
            ),
            (
                "يسعدني تواصلك. خلينا نضيق الشغل بسرعة: "
                "**تشتري للسكن ولا للاستثمار؟** وبعدها نثبت الميزانية والمنطقة."
            ),
            (
                "تمام — عشان أخدمك كمستشار مبيعات: محتاج **٣ معلومات**: نطاق سعر تقريبي، المنطقة، ونوع الوحدة المفضل. "
                "ممكن تذكرهم باختصار؟"
            ),
        ]
        if turns <= 1:
            return openers[0]
        if turns == 2:
            return openers[1]
        return openers[2]

    def _sales_reply_en(
        self,
        last: str,
        b: Optional[str],
        loc: Optional[str],
        pt: Optional[str],
        proj: Optional[str],
        turns: int,
        t: str,
    ) -> str:
        if any(x in t for x in ("expensive", "too much", "cannot", "can't")):
            return (
                "I hear you on price — payment plans often make monthly cash flow much easier. "
                "What **maximum monthly installment** feels comfortable? I’ll narrow options to realistic matches."
            )
        if _looks_like_scheduling_message(last, "en"):
            loc_echo = f" Noted you prefer **{loc}**." if loc else ""
            pt_echo = f"Unit type: **{pt}**." if pt else ""
            return (
                "Got it — I've captured the **time window** you suggested for a viewing."
                + loc_echo
                + (f" {pt_echo}" if pt_echo else "")
                + " Next step: our sales team will **confirm the slot** and suggest the closest matching project. "
                "Share a **best phone number** or any notes for the rep if you'd like."
            )
        if "visit" in t or "viewing" in t:
            return (
                "Perfect — viewings usually clarify the decision. "
                "Share **preferred days** (weekday/weekend, morning/evening) and I'll suggest the cleanest next step."
            )
        if b and loc:
            extra = f" Property type: {pt}." if pt else ""
            pr = f" Noted interest in **{proj}**." if proj else ""
            return (
                f"Great — budget **{b}** and area **{loc}**.{extra}{pr} "
                "Next step: I’ll align 2–3 best-fit options. Do you prefer **faster handover** or **best value per sqm**?"
            )
        if b and not loc:
            return (
                f"Thanks — budget **{b}** is clear. Which **areas** are you considering "
                "(e.g. Sheikh Zayed, New Cairo, October)?"
            )
        if loc and not b:
            return (
                f"Nice — **{loc}** has several strong projects. What **approximate budget range** should I stay within?"
            )
        if any(
            x in t
            for x in (
                "recommend",
                "suggest project",
                "show me project",
                "project ideas",
            )
        ):
            return (
                "Got it — I’ll line up **recommendations** that fit you. To make them realistic (not random), "
                "I need your **approximate budget** and **preferred area** (e.g. Sheikh Zayed, New Cairo). "
                "Optional: **apartment vs villa** and **to live vs invest**."
            )
        opts = [
            "Hi — I’ll guide you like a sales consultant. To start: what’s your **budget range** and **preferred area**?",
            "Glad you reached out. Quick question: is this **for living or investment**? Then we lock budget + area.",
            "To recommend precisely, I need **budget range**, **area**, and **unit type** — can you share them in one line?",
        ]
        return opts[min(turns, len(opts) - 1)]
