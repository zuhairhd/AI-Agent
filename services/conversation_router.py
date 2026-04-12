"""
Conversation router for phone calls.

Responsibilities
----------------
- Detect intent fast before using the LLM
- Return direct short spoken replies for common business intents
- Use LLM only when needed
- Create clean follow-up signals for leads/inquiries
- Keep replies short and phone-friendly
- Avoid awkward bot-like behavior
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from django.conf import settings
from openai import OpenAI

from services.intent_engine import detect_intent, normalize_language

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-4o"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _company_name() -> str:
    from apps.portal.models import SiteConfig
    return SiteConfig.get_solo().company_name


def _follow_up_dict(enabled: bool = False, kind: str = "", note: str = "") -> Dict[str, Any]:
    return {
        "follow_up": enabled,
        "follow_up_type": kind,
        "follow_up_note": note,
    }


def _closing_reply(language: str) -> str:
    company = _company_name()
    if language == "ar":
        return f"شكرًا لاتصالك بـ {company}. مع السلامة."
    return f"Thank you for calling {company}. Goodbye."


def _transfer_reply(language: str) -> str:
    if language == "ar":
        return "أفهم أنك ترغب في التحدث مع أحد أعضاء الفريق. يرجى الانتظار بينما أقوم بتحويلك."
    return "I understand you'd like to speak with a team member. Please hold while I transfer you."


def _clean_phone_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^[\-\*\d\.\)\s]+", "", text, flags=re.M)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # remove annoying fillers
    annoying = ["من فضلك", "لحظة", "please", "kindly"]
    for word in annoying:
        text = text.replace(word, "")
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _shorten_for_phone(text: str, language: str) -> str:
    if not text:
        return text

    text = _clean_phone_text(text)
    max_len = 140 if language == "ar" else 180

    if len(text) <= max_len:
        return text

    return text[:max_len].rsplit(" ", 1)[0].strip()


def _parse_tokens(reply: str) -> Dict[str, Any]:
    lines = (reply or "").strip().splitlines()

    transfer = False
    reason = ""
    closing = False
    no_answer = False
    clean_lines = []

    for line in lines:
        s = line.strip()

        if s.startswith("[TRANSFER]"):
            transfer = True
            reason = s[len("[TRANSFER]"):].lstrip(":").strip() or "llm_transfer"
        elif s == "[CLOSING]":
            closing = True
        elif s == "[NO_ANSWER]":
            no_answer = True
        else:
            clean_lines.append(line)

    clean_reply = " ".join(" ".join(clean_lines).split()).strip()

    return {
        "clean_reply": clean_reply,
        "transfer": transfer,
        "reason": reason,
        "closing": closing,
        "rag_no_answer": no_answer,
    }


# ---------------------------------------------------------------------------
# Direct intent replies
# ---------------------------------------------------------------------------

def _intent_reply(intent_data: Dict[str, Any], question: str, language: str) -> Dict[str, Any] | None:
    intent = intent_data["intent"]
    entities = intent_data.get("entities", {})

    from apps.portal.models import SiteConfig
    _cfg = SiteConfig.get_solo()
    _product = _cfg.product_name
    _hours = _cfg.office_hours

    if language == "ar":
        mapping = {
            "closing": {
                "answer": _closing_reply(language),
                "transfer": False,
                "reason": "",
                "closing": True,
                "rag_no_answer": False,
                **_follow_up_dict(False, "", ""),
            },
            "human_transfer": {
                "answer": _transfer_reply(language),
                "transfer": True,
                "reason": "intent:human_transfer",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "callback", "المتصل طلب التحدث مع شخص حقيقي."),
            },
            "office_visit": {
                "answer": "يسعدنا استقبالكم خلال أوقات العمل من الأحد إلى الخميس من 9 صباحًا إلى 5 مساءً. هل تفضل زيارة المكتب أم تواصل فريقنا معك؟",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "office_visit", "المتصل سأل عن زيارة المكتب أو طلب زيارة."),
            },
            "product_info": {
                "answer": f"{_product} يرد على مكالمات عملك تلقائيًا ويخدم عملاءك على مدار الساعة. غالبًا الباقة القياسية هي الأنسب لمعظم الشركات. هل تحب أعرفك عليها؟",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "inquiry", "المتصل سأل عن المنتج أو الخدمة."),
            },
            "best_package": {
                "answer": "عادةً نرشح الباقة القياسية لأنها الأنسب لمعظم الشركات من حيث التوازن بين السعر والمزايا. هل ترغب في معرفة السعر؟",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "pricing", "المتصل سأل عن أفضل باقة."),
            },
            "pricing": {
                "answer": "لدينا باقات مختلفة حسب حجم العمل، وغالبًا الباقة القياسية هي الأفضل توازنًا. هل تحب يرتب لك فريقنا عرضًا مناسبًا؟",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "pricing", "المتصل سأل عن السعر أو التكلفة."),
            },
            "lead_interest": {
                "answer": "ممتاز، أقدر أسجل طلبك الآن ليتم التواصل معك. هل تفضل رقمك الحالي أم رقمًا آخر؟",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "lead", "المتصل أبدى اهتمامًا واضحًا."),
            },
            "clarification": {
                "answer": "بكل بساطة، الخدمة ترد على مكالمات العملاء تلقائيًا وتساعد الشركات على عدم فقدان أي اتصال. هل ترغب أن أشرح الباقة القياسية؟",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "inquiry", "المتصل طلب توضيحًا أبسط."),
            },
            "package_details": {
                "basic": {
                    "answer": "الباقة الأساسية مناسبة للمشاريع الصغيرة جدًا أو لمن يبدأ بالأتمتة البسيطة. هل ترغب في معرفة السعر أيضًا؟",
                    "transfer": False,
                    "reason": "",
                    "closing": False,
                    "rag_no_answer": False,
                    **_follow_up_dict(True, "pricing", "المتصل سأل عن الباقة الأساسية."),
                },
                "standard": {
                    "answer": "الباقة القياسية هي الأكثر توصية لمعظم الشركات لأنها تجمع بين السعر المناسب والمزايا العملية. هل ترغب في معرفة السعر؟",
                    "transfer": False,
                    "reason": "",
                    "closing": False,
                    "rag_no_answer": False,
                    **_follow_up_dict(True, "pricing", "المتصل سأل عن الباقة القياسية."),
                },
                "premium": {
                    "answer": "الباقة المتقدمة مناسبة للشركات الأكبر أو ذات حجم المكالمات المرتفع. هل ترغب في ملخص سريع عن السعر؟",
                    "transfer": False,
                    "reason": "",
                    "closing": False,
                    "rag_no_answer": False,
                    **_follow_up_dict(True, "pricing", "المتصل سأل عن الباقة المتقدمة."),
                },
            },
        }

        if intent == "package_details":
            return mapping["package_details"].get(entities.get("package", "standard"))

        return mapping.get(intent)

    mapping = {
        "closing": {
            "answer": _closing_reply(language),
            "transfer": False,
            "reason": "",
            "closing": True,
            "rag_no_answer": False,
            **_follow_up_dict(False, "", ""),
        },
        "human_transfer": {
            "answer": _transfer_reply(language),
            "transfer": True,
            "reason": "intent:human_transfer",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "callback", "Caller requested a human agent."),
        },
        "office_visit": {
            "answer": f"You’re welcome to visit us during office hours, {_hours}. Would you prefer to visit the office or have our team contact you?",
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "office_visit", "Caller asked about visiting the office."),
        },
        "product_info": {
            "answer": f"{_product} answers business calls automatically and helps serve customers around the clock. The Standard package is usually the best fit for most businesses. Would you like a quick overview?",
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "inquiry", "Caller asked about the product."),
        },
        "best_package": {
            "answer": "We usually recommend the Standard package because it offers the best balance between cost and features for most businesses. Would you like the pricing details?",
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "pricing", "Caller asked about the best package."),
        },
        "pricing": {
            "answer": "We have different packages depending on business size, and the Standard package is usually the best fit for most businesses. Would you like our team to follow up with pricing details?",
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "pricing", "Caller asked about pricing."),
        },
        "lead_interest": {
            "answer": "Great, I can register your request now so our team can contact you. Would you like to use your current number or another one?",
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "lead", "Caller showed clear interest."),
        },
        "clarification": {
            "answer": "Simply put, the service answers business calls automatically and helps collect customer details. Would you like me to explain the Standard package?",
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
            **_follow_up_dict(True, "inquiry", "Caller asked for a simpler explanation."),
        },
        "package_details": {
            "basic": {
                "answer": "The Basic package is suitable for very small businesses or businesses starting with simple automation. Would you like the pricing details too?",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "pricing", "Caller asked about the Basic package."),
            },
            "standard": {
                "answer": "The Standard package is our most recommended option because it gives a strong balance between price and practical features. Would you like the pricing details?",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "pricing", "Caller asked about the Standard package."),
            },
            "premium": {
                "answer": "The Premium package is suitable for larger businesses or higher call volume. Would you like a quick pricing summary?",
                "transfer": False,
                "reason": "",
                "closing": False,
                "rag_no_answer": False,
                **_follow_up_dict(True, "pricing", "Caller asked about the Premium package."),
            },
        },
    }

    if intent == "package_details":
        return mapping["package_details"].get(entities.get("package", "standard"))

    return mapping.get(intent)


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _build_messages(question: str, history: List[dict], language: str) -> List[dict]:
    company = _company_name()

    if language == "ar":
        system = (
            f'أنت موظف استقبال هاتفي محترف لشركة "{company}". '
            "تحدث بالعربية فقط. "
            "اجعل الرد قصير جدًا من جملة أو جملتين. "
            "تحدث بطريقة طبيعية وواثقة مثل موظف استقبال. "
            "لا تشرح كثيرًا. "
            "وجه العميل بلطف نحو الباقة القياسية عند الحاجة. "
            "لا تذكر الملفات أو النظام الداخلي أو المستندات. "
            "إذا لم تعرف الإجابة بثقة، أضف [NO_ANSWER] في سطر مستقل. "
            "إذا احتاج تحويل أضف [TRANSFER]: reason في سطر مستقل. "
            "إذا أنهى المتصل المكالمة أضف [CLOSING] في سطر مستقل."
        )
    else:
        system = (
            f'You are a professional phone receptionist for "{company}". '
            "Respond only in English. "
            "Keep replies VERY short, usually 1 to 2 sentences. "
            "Sound natural and confident. "
            "Do not over-explain. "
            "Gently guide customers toward the Standard package when appropriate. "
            "Do not mention files, uploads, or internal systems. "
            "If unsure add [NO_ANSWER] on its own line. "
            "If transfer is needed add [TRANSFER]: reason on its own line. "
            "If the conversation ends add [CLOSING] on its own line."
        )

    messages = [{"role": "system", "content": system}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": question})
    return messages


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def route_turn(
    question: str,
    history: List[dict],
    vector_store_id: str,
    language: str = "en",
) -> Dict[str, Any]:
    """
    Main router:
    1) detect intent fast
    2) return direct answer if possible
    3) otherwise use LLM with RAG
    """
    language = normalize_language(language)
    question = (question or "").strip()

    intent_data = detect_intent(question, language=language)
    direct = _intent_reply(intent_data, question, language)

    if direct:
        # Don't repeat the exact same canned answer that was already given last turn
        candidate = (direct.get("answer") or "")[:80]
        if candidate:
            last_assistant = next(
                (m["content"] for m in reversed(history) if m.get("role") == "assistant"),
                "",
            )
            if last_assistant and last_assistant.startswith(candidate):
                logger.debug(f"route_turn: skipping repeated canned answer for intent={intent_data.get('intent')}")
                direct = None

    if direct:
        return direct

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    current_vector_store_id = (
        getattr(settings, "OPENAI_VECTOR_STORE_ID", "").strip()
        or (vector_store_id or "").strip()
    )
    messages = _build_messages(question, history, language)

    try:
        if current_vector_store_id:
            try:
                response = client.responses.create(
                    model=MODEL_NAME,
                    input=messages,
                    max_output_tokens=110 if language == "ar" else 150,
                    tools=[{
                        "type": "file_search",
                        "vector_store_ids": [current_vector_store_id],
                    }],
                )
                raw_reply = response.output_text.strip()
            except Exception as exc:
                logger.warning(f"RAG response failed, fallback to plain chat: {exc}")
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=110 if language == "ar" else 150,
                    temperature=0.3,
                )
                raw_reply = completion.choices[0].message.content.strip()
        else:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=110 if language == "ar" else 150,
                temperature=0.3,
            )
            raw_reply = completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error(f"route_turn failed: {exc}", exc_info=True)
        raise

    parsed = _parse_tokens(raw_reply)
    clean_reply = _shorten_for_phone(parsed["clean_reply"], language)

    # Guard: tokens-only reply leaves clean_reply empty — provide a spoken fallback
    if not clean_reply:
        if parsed["closing"]:
            clean_reply = _closing_reply(language)
        elif parsed["transfer"]:
            clean_reply = _transfer_reply(language)
        else:
            clean_reply = (
                "لا تتوفر لديّ المعلومات الكافية حاليًا، سيتواصل معك فريقنا قريبًا."
                if language == "ar"
                else "I don't have enough information on that right now. Our team will follow up with you."
            )
        logger.debug(f"route_turn: used fallback reply for empty clean_reply (raw={raw_reply!r})")

    follow_up = False
    follow_up_type = ""
    follow_up_note = ""

    q_low = question.lower()
    if parsed["rag_no_answer"]:
        follow_up = True
        follow_up_type = "inquiry"
        follow_up_note = "استفسار يحتاج متابعة بشرية." if language == "ar" else "Inquiry needs human follow-up."
    elif any(x in q_low for x in ["price", "pricing", "cost", "package", "demo", "interested", "contact"]) or \
         any(x in question for x in ["السعر", "الأسعار", "الباقة", "الباقات", "مهتم", "تفاصيل", "عرض", "تواصل"]):
        follow_up = True
        follow_up_type = "lead"
        follow_up_note = "عميل محتمل مهتم بالسعر أو الباقات." if language == "ar" else "Potential lead asking about pricing or packages."

    return {
        "answer": clean_reply,
        "transfer": parsed["transfer"],
        "reason": parsed["reason"],
        "closing": parsed["closing"],
        "rag_no_answer": parsed["rag_no_answer"],
        "follow_up": follow_up,
        "follow_up_type": follow_up_type,
        "follow_up_note": follow_up_note,
    }
