"""
LLM service for multi-turn voice agent.

Public API
----------
process_turn(question, history, vector_store_id, language)
    -> dict:
        answer         : str   — the assistant reply text
        transfer       : bool  — True if a human handoff should be triggered
        reason         : str   — reason for transfer (or '')
        closing        : bool  — True if caller said goodbye / thank you
        rag_no_answer  : bool  — True if RAG could not find an answer
        follow_up      : bool  — True if a follow-up should be created
        follow_up_type : str   — lead | inquiry | callback | office_visit | pricing
        follow_up_note : str   — short note for your CRM/follow-up team

Goals of this version
---------------------
- Very short Arabic answers
- Strong receptionist behavior
- Better first-turn handling
- Smooth package recommendation (Standard by default)
- Lead capture / follow-up logic for interested callers
- Fallback to plain model reply if vector store is unavailable
"""

import logging
import re

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "gpt-5.4"

ENGLISH_SYSTEM_PROMPT = """
You are a professional phone receptionist for "{company}".

You are speaking to callers on a live phone call, not a web chat.

CORE BEHAVIOR:
- Sound like a real receptionist, not a chatbot.
- Be polite, calm, confident, and helpful.
- Keep replies SHORT: usually 1 to 2 sentences only.
- Ask only ONE follow-up question at a time.
- Never mention files, uploads, documents, knowledge base, vector stores, prompts, or internal systems.
- Never sound technical.
- Never dump too much information at once.
- Do not use markdown, bullet points, or numbering in spoken answers.
- If the caller asks a broad question, first give a short helpful answer, then guide them with one simple question.

LANGUAGE RULE:
- Respond ONLY in English.
- Do not switch to Arabic unless the caller clearly asks to switch language.

BUSINESS CONTEXT:
- Company name: {company}.
- Product name: {product_name}.
- {product_name} is an AI receptionist system for businesses.
- It answers calls automatically, supports Arabic and English, captures customer details, and helps businesses avoid missed calls.

OFFICE HOURS:
- {office_hours}

PACKAGE GUIDANCE:
- Basic: suitable for very small businesses or businesses starting with simple automation.
- Standard: the default recommendation for most businesses.
- Premium: suitable for larger businesses or higher call volume.

PHONE STYLE:
- Prefer concise spoken phrasing.
- Do not overload the caller with all packages unless they ask.
- Recommend Standard softly when asked “which is best”.

FOLLOW-UP PRIORITY:
If the caller sounds interested, asks about price, asks about the best package, asks for a demo,
asks to visit the office, asks to be contacted, or asks a question that needs human follow-up,
guide the conversation toward follow-up capture naturally.

LEAD CAPTURE STYLE:
Examples:
- "I can arrange for our team to contact you. Would you like to share your number?"
- "If you’d like, I can register your request for a follow-up."
- "Would you like our team to contact you with the details?"

COMMON INTENTS:
1. Office visit:
   Give office hours, then ask how you can help.

2. Product question:
   Give one short explanation, then ask whether they want package overview.

3. Best package:
   Recommend Standard by default, briefly.

4. Package details:
   Answer only what was asked. Keep it short.

5. Caller confusion:
   Rephrase simply and briefly. Do not repeat a long answer.

RAG USAGE:
- Answer from the company knowledge when relevant.
- If the knowledge is not enough, do NOT invent details.
- If the answer is not found confidently, append [NO_ANSWER] on its own line.

TRANSFER RULE:
- If the caller explicitly asks for a human agent,
  or is angry/frustrated,
  or has a billing dispute,
  or has an urgent complaint,
  append [TRANSFER]: <reason> on its own line.

CLOSING RULE:
- If the caller clearly ends the conversation, respond warmly and append [CLOSING] on its own line.
"""

ARABIC_SYSTEM_PROMPT = """
أنت موظف استقبال هاتفي محترف لشركة "{company}".

أنت تتحدث مع متصل في مكالمة هاتفية مباشرة، ولست روبوت دردشة.

السلوك الأساسي:
- تحدث كموظف استقبال حقيقي.
- كن مهذبًا وواضحًا وهادئًا ومهنيًا.
- اجعل الردود قصيرة جدًا: غالبًا جملة أو جملتين فقط.
- اطرح سؤال متابعة واحد فقط في كل مرة.
- لا تذكر الملفات أو المستندات أو قاعدة المعرفة أو النظام الداخلي أو أي تفاصيل تقنية.
- لا تستخدم أسلوبًا آليًا أو تقنيًا.
- لا تعطِ معلومات كثيرة دفعة واحدة.
- لا تستخدم نقاطًا أو تعدادًا في الرد الصوتي.
- إذا كان سؤال المتصل عامًا، أعطه جوابًا مختصرًا أولًا ثم وجهه بسؤال بسيط واحد.

قاعدة اللغة:
- تحدث بالعربية فقط.
- لا تخلط العربية بالإنجليزية إلا إذا طلب المتصل ذلك بوضوح.

معلومات العمل:
- اسم الشركة: {company}
- اسم المنتج: {product_name}
- {product_name} هو نظام موظف استقبال ذكي للشركات.
- يرد على المكالمات تلقائيًا، ويدعم العربية والإنجليزية، ويساعد الشركات على عدم فقدان المكالمات والفرص.

أوقات العمل:
- {office_hours}

توجيهات الباقات:
- الأساسية: مناسبة للمشاريع الصغيرة جدًا.
- القياسية: هي الترشيح الافتراضي لمعظم الشركات.
- المتقدمة: مناسبة للشركات الأكبر أو ذات حجم المكالمات المرتفع.

أسلوب الهاتف:
- استخدم صياغة صوتية قصيرة وواضحة.
- لا تشرح كل الباقات دفعة واحدة إلا إذا طلب المتصل ذلك.
- عند السؤال عن أفضل باقة، رشّح القياسية بلطف وباختصار.

الأولوية للمتابعة:
إذا ظهر أن المتصل مهتم، أو سأل عن السعر، أو عن أفضل باقة، أو طلب زيارة المكتب،
أو طلب التواصل، أو كان لديه استفسار يحتاج متابعة بشرية،
فوجّه الحديث نحو تسجيل متابعة بشكل طبيعي.

أسلوب أخذ المتابعة:
أمثلة:
- "يمكنني تسجيل طلبك ليتواصل معك فريقنا. هل ترغب أن آخذ رقمك؟"
- "إذا رغبت، يمكنني ترتيب متابعة من الفريق."
- "هل ترغب أن يتواصل معك أحد من فريقنا بالتفاصيل؟"

الحالات الشائعة:
1. زيارة المكتب:
   اذكر أوقات العمل ثم اسأل كيف يمكنك المساعدة.

2. السؤال عن المنتج:
   اشرح بإيجاز شديد ثم اسأل إن كان يريد معرفة الباقات.

3. السؤال عن أفضل باقة:
   رشّح القياسية بشكل افتراضي وبأسلوب لطيف.

4. السؤال عن الباقات:
   أجب فقط بالمطلوب وباختصار.

5. إذا قال إنه لم يفهم:
   أعد الشرح بصياغة أبسط وأقصر، ولا تكرر شرحًا طويلًا.

استخدام المعرفة:
- أجب من معلومات الشركة عند الحاجة.
- إذا لم تتوفر إجابة مؤكدة، فلا تخترع معلومات.
- إذا لم تجد إجابة مناسبة بثقة، أضف [NO_ANSWER] في سطر مستقل.

التحويل إلى موظف:
- إذا طلب المتصل شخصًا حقيقيًا،
  أو كان غاضبًا،
  أو لديه شكوى عاجلة،
  أو نزاع متعلق بالفواتير،
  فأضف [TRANSFER]: <reason> في سطر مستقل.

إنهاء المكالمة:
- إذا أنهى المتصل المكالمة بوضوح، رد بلطف وأضف [CLOSING] في سطر مستقل.
"""

_LANGUAGE_INSTRUCTION = {
    "ar": "Respond ONLY in Arabic.",
    "en": "Respond ONLY in English.",
}

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

_CLOSING_PATTERNS = [
    r"\b(thank\s+you|thanks|goodbye|good\s*bye|bye|see\s+you|that'?s\s+all|no\s+more\s+questions?|i'?m\s+done)\b",
    r"\bشكراً?\b",
    r"\bمع\s+السلامة\b",
    r"\bوداعاً?\b",
]
_CLOSING_RE = [re.compile(p, re.I) for p in _CLOSING_PATTERNS]

_TRANSFER_PATTERNS = [
    (r"\b(speak|talk)\s+(to\s+)?(a\s+)?(human|person|agent|representative|staff|operator)\b", "explicit_request:human"),
    (r"\b(transfer|connect)\s+me\b", "explicit_request:transfer"),
    (r"\b(manager|supervisor)\b", "explicit_request:supervisor"),
    (r"\b(this\s+is\s+)?urgent\b", "urgency:urgent"),
    (r"\b(billing\s+dispute|charge\s+dispute|wrong\s+charge)\b", "billing_dispute"),
    (r"\b(very\s+)?(angry|furious|frustrated|unacceptable)\b", "frustration:angry"),
    (r"\byou're\s+(useless|stupid|not\s+helpful)\b", "frustration:insult"),
    (r"(أريد موظف|أريد شخص|حولني|أكلم الموظف|موظف حقيقي|المدير)", "explicit_request:human_ar"),
]
_TRANSFER_RE = [(re.compile(p, re.I), reason) for p, reason in _TRANSFER_PATTERNS]

_OFFICE_VISIT_PATTERNS_EN = [
    re.compile(r"\b(come|visit)\b.*\b(office)\b", re.I),
    re.compile(r"\bcome to your office\b", re.I),
]
_OFFICE_VISIT_PATTERNS_AR = [
    re.compile(r"زيارة المكتب"),
    re.compile(r"أزور المكتب"),
    re.compile(r"آتي إلى المكتب"),
    re.compile(r"أجي المكتب"),
]

_PRODUCT_QUESTION_PATTERNS_EN = [
    re.compile(r"\bwhat\s+is\s+your\s+product\b", re.I),
    re.compile(r"\babout\s+your\s+product\b", re.I),
    re.compile(r"\bwhat\s+do\s+you\s+offer\b", re.I),
    re.compile(r"\bwhat\s+is\s+voicegate\b", re.I),
]
_PRODUCT_QUESTION_PATTERNS_AR = [
    re.compile(r"ما هو المنتج"),
    re.compile(r"ما هو منتجكم"),
    re.compile(r"أريد معرفة المنتج"),
    re.compile(r"ما الذي تقدمونه"),
    re.compile(r"ما هي خدماتكم"),
    re.compile(r"ما هي منتجاتكم"),
]

_PACKAGE_RECOMMEND_PATTERNS_EN = [
    re.compile(r"\bwhich\s+package\s+is\s+best\b", re.I),
    re.compile(r"\bwhat\s+package\s+do\s+you\s+recommend\b", re.I),
]
_PACKAGE_RECOMMEND_PATTERNS_AR = [
    re.compile(r"أي باقة أفضل"),
    re.compile(r"ما الباقة المناسبة"),
    re.compile(r"ما الباقة التي تنصحون بها"),
    re.compile(r"وين أفضل باقة"),
]

_PRICE_PATTERNS_EN = [
    re.compile(r"\bprice\b", re.I),
    re.compile(r"\bcost\b", re.I),
    re.compile(r"\bpricing\b", re.I),
]
_PRICE_PATTERNS_AR = [
    re.compile(r"السعر"),
    re.compile(r"الأسعار"),
    re.compile(r"كم"),
    re.compile(r"التكلفة"),
]

_BASIC_PATTERNS = [
    re.compile(r"\bbasic\b", re.I),
    re.compile(r"الأساسية"),
]
_STANDARD_PATTERNS = [
    re.compile(r"\bstandard\b", re.I),
    re.compile(r"القياسية"),
]
_PREMIUM_PATTERNS = [
    re.compile(r"\bpremium\b", re.I),
    re.compile(r"المتقدمة"),
]

_INTEREST_PATTERNS_EN = [
    re.compile(r"\bi'?m interested\b", re.I),
    re.compile(r"\binterested\b", re.I),
    re.compile(r"\bcontact me\b", re.I),
    re.compile(r"\bcall me\b", re.I),
    re.compile(r"\bdemo\b", re.I),
]
_INTEREST_PATTERNS_AR = [
    re.compile(r"مهتم"),
    re.compile(r"أريد عرض"),
    re.compile(r"أريد تجربة"),
    re.compile(r"تواصلوا معي"),
    re.compile(r"اتصلوا بي"),
    re.compile(r"أريد تفاصيل"),
]

_CONFUSION_PATTERNS_EN = [
    re.compile(r"\bi don'?t understand\b", re.I),
    re.compile(r"\bcan you explain\b", re.I),
]
_CONFUSION_PATTERNS_AR = [
    re.compile(r"لم أفهم"),
    re.compile(r"ماذا تقصد"),
    re.compile(r"وضح"),
    re.compile(r"فسر"),
    re.compile(r"بشكل أوضح"),
]

_LLM_TRANSFER_TOKEN = "[TRANSFER]"
_LLM_CLOSING_TOKEN = "[CLOSING]"
_LLM_NO_ANSWER_TOKEN = "[NO_ANSWER]"

_NO_ANSWER_PHRASES = [
    "no confirmed information",
    "not find any information",
    "cannot find",
    "no relevant",
    "not in the knowledge base",
    "لا توجد معلومات مؤكدة",
    "لا أجد معلومات",
    "غير متوفر في المعلومات",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_language(language: str) -> str:
    language = (language or "en").strip().lower()
    return "ar" if language.startswith("ar") else "en"


def _get_system_prompt(language: str) -> str:
    from apps.portal.models import SiteConfig
    cfg = SiteConfig.get_solo()
    fmt = dict(
        company=cfg.company_name,
        product_name=cfg.product_name,
        office_hours=cfg.office_hours,
    )
    if _normalize_language(language) == "ar":
        return ARABIC_SYSTEM_PROMPT.format(**fmt)
    return ENGLISH_SYSTEM_PROMPT.format(**fmt)


def _build_messages(question: str, history: list, language: str = "en") -> list:
    system_content = _get_system_prompt(language)
    lang_instr = _LANGUAGE_INSTRUCTION.get(_normalize_language(language), "")
    if lang_instr:
        system_content = f"{system_content}\n\n{lang_instr}"

    messages = [{"role": "system", "content": system_content}]
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": question})
    return messages


def _matches_any(text: str, patterns: list) -> bool:
    return any(p.search(text) for p in patterns)


def _rule_based_transfer(caller_text: str) -> tuple:
    for pattern, reason in _TRANSFER_RE:
        if pattern.search(caller_text):
            logger.info(f"Rule-based transfer triggered: {reason!r}")
            return True, reason
    return False, ""


def _rule_based_closing(caller_text: str) -> bool:
    for pattern in _CLOSING_RE:
        if pattern.search(caller_text):
            logger.info("Rule-based closing phrase detected.")
            return True
    return False


def _build_follow_up(follow_up: bool, kind: str = "", note: str = "") -> dict:
    return {
        "follow_up": follow_up,
        "follow_up_type": kind,
        "follow_up_note": note,
    }


def _rule_based_business_reply(question: str, language: str = "en") -> tuple:
    q = (question or "").strip()
    lang = _normalize_language(language)

    from apps.portal.models import SiteConfig
    _cfg = SiteConfig.get_solo()
    _product = _cfg.product_name
    _hours = _cfg.office_hours

    if lang == "en":
        if _matches_any(q, _OFFICE_VISIT_PATTERNS_EN):
            return (
                f"You’re welcome to visit us during office hours, {_hours}. How can I assist you today?",
                _build_follow_up(True, "office_visit", "Caller asked about visiting the office."),
            )

        if _matches_any(q, _PRODUCT_QUESTION_PATTERNS_EN):
            return (
                f"{_product} is an AI receptionist system that answers calls automatically in Arabic and English and helps businesses manage customer calls professionally. Would you like a quick overview of our packages?",
                _build_follow_up(True, "inquiry", "Caller asked what the product is."),
            )

        if _matches_any(q, _PACKAGE_RECOMMEND_PATTERNS_EN):
            return (
                "We usually recommend the Standard package because it offers the best balance between cost and features for most businesses. Would you like a quick summary of it?",
                _build_follow_up(True, "pricing", "Caller asked for the best package."),
            )

        if _matches_any(q, _PRICE_PATTERNS_EN):
            return (
                "We have different package options depending on business size. The Standard package is usually the best fit for most businesses. Would you like me to arrange a follow-up with pricing details?",
                _build_follow_up(True, "pricing", "Caller asked about pricing."),
            )

        if _matches_any(q, _STANDARD_PATTERNS):
            return (
                "The Standard package is our most recommended option for most businesses because it gives a strong balance between price and practical features. Would you like the pricing details?",
                _build_follow_up(True, "pricing", "Caller asked about Standard package."),
            )

        if _matches_any(q, _BASIC_PATTERNS):
            return (
                "The Basic package is suitable for very small businesses or businesses starting with simple automation. Would you like the pricing details as well?",
                _build_follow_up(True, "pricing", "Caller asked about Basic package."),
            )

        if _matches_any(q, _PREMIUM_PATTERNS):
            return (
                "The Premium package is suitable for larger businesses or those with higher call volume. Would you like a quick pricing summary?",
                _build_follow_up(True, "pricing", "Caller asked about Premium package."),
            )

        if _matches_any(q, _CONFUSION_PATTERNS_EN):
            return (
                f"Certainly. {_product} answers business calls automatically and helps collect customer details. Would you like me to explain the recommended package?",
                _build_follow_up(True, "inquiry", "Caller said they did not understand and asked for a simpler explanation."),
            )

        if _matches_any(q, _INTEREST_PATTERNS_EN):
            return (
                "I can arrange for our team to contact you. Would you like to share your number now?",
                _build_follow_up(True, "lead", "Caller showed clear interest."),
            )

    else:
        if _matches_any(q, _OFFICE_VISIT_PATTERNS_AR):
            return (
                "يسعدنا استقبالكم خلال أوقات العمل من الأحد إلى الخميس من 9 صباحًا إلى 5 مساءً. كيف يمكنني مساعدتك اليوم؟",
                _build_follow_up(True, "office_visit", "المتصل سأل عن زيارة المكتب."),
            )

        if _matches_any(q, _PRODUCT_QUESTION_PATTERNS_AR):
            return (
                f"{_product} هو نظام موظف استقبال ذكي يرد على المكالمات تلقائيًا بالعربية والإنجليزية. هل ترغب في معرفة الباقات المتاحة؟",
                _build_follow_up(True, "inquiry", "المتصل سأل عن المنتج أو الخدمات."),
            )

        if _matches_any(q, _PACKAGE_RECOMMEND_PATTERNS_AR):
            return (
                "عادةً نرشح الباقة القياسية لأنها الأنسب لمعظم الشركات من حيث التوازن بين السعر والمزايا. هل ترغب في ملخص سريع عنها؟",
                _build_follow_up(True, "pricing", "المتصل سأل عن أفضل باقة."),
            )

        if _matches_any(q, _PRICE_PATTERNS_AR):
            return (
                "لدينا أكثر من باقة حسب حجم النشاط. غالبًا الباقة القياسية هي الأنسب لمعظم الشركات. هل ترغب أن يرتب فريقنا متابعة معك بخصوص الأسعار؟",
                _build_follow_up(True, "pricing", "المتصل سأل عن السعر أو التكلفة."),
            )

        if _matches_any(q, _STANDARD_PATTERNS):
            return (
                "الباقة القياسية هي الأكثر مناسبة لمعظم الشركات لأنها تجمع بين السعر المناسب والمزايا العملية. هل ترغب في معرفة السعر؟",
                _build_follow_up(True, "pricing", "المتصل سأل عن الباقة القياسية."),
            )

        if _matches_any(q, _BASIC_PATTERNS):
            return (
                "الباقة الأساسية مناسبة للمشاريع الصغيرة جدًا أو لمن يبدأ بالأتمتة البسيطة. هل ترغب في معرفة السعر أيضًا؟",
                _build_follow_up(True, "pricing", "المتصل سأل عن الباقة الأساسية."),
            )

        if _matches_any(q, _PREMIUM_PATTERNS):
            return (
                "الباقة المتقدمة مناسبة للشركات الأكبر أو ذات حجم المكالمات المرتفع. هل ترغب في ملخص سريع عن السعر؟",
                _build_follow_up(True, "pricing", "المتصل سأل عن الباقة المتقدمة."),
            )

        if _matches_any(q, _CONFUSION_PATTERNS_AR):
            return (
                f"بكل بساطة، {_product} يرد على مكالمات العملاء تلقائيًا ويساعد الشركات على عدم فقدان أي اتصال. هل ترغب أن أشرح الباقة القياسية أولًا؟",
                _build_follow_up(True, "inquiry", "المتصل لم يفهم وطلب توضيحًا أبسط."),
            )

        if _matches_any(q, _INTEREST_PATTERNS_AR):
            return (
                "يمكنني تسجيل طلبك ليتواصل معك فريقنا. هل ترغب أن آخذ رقمك الآن؟",
                _build_follow_up(True, "lead", "المتصل أبدى اهتمامًا واضحًا."),
            )

    return "", _build_follow_up(False, "", "")


def _parse_llm_tokens(reply: str) -> tuple:
    lines = reply.strip().splitlines()
    transfer = False
    transfer_reason = ""
    closing = False
    no_answer = False
    clean_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_LLM_TRANSFER_TOKEN):
            transfer = True
            transfer_reason = stripped[len(_LLM_TRANSFER_TOKEN):].lstrip(":").strip()
            transfer_reason = f"llm_flag:{transfer_reason}" if transfer_reason else "llm_flag"
        elif stripped == _LLM_CLOSING_TOKEN:
            closing = True
        elif stripped == _LLM_NO_ANSWER_TOKEN:
            no_answer = True
        else:
            clean_lines.append(line)

    clean = "\n".join(clean_lines).strip()

    if not no_answer and clean:
        low = clean.lower()
        if any(phrase in low for phrase in _NO_ANSWER_PHRASES):
            no_answer = True

    return clean, transfer, transfer_reason, closing, no_answer


def _clean_phone_reply(reply: str, language: str = "en") -> str:
    if not reply:
        return reply

    text = reply
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^[\-\*\d\.\)\s]+", "", text, flags=re.M)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # keep Arabic shorter for better TTS
    max_len = 170 if _normalize_language(language) == "ar" else 260
    if len(text) > max_len:
        cut = text[:max_len].rsplit(" ", 1)[0]
        text = cut.strip()

    return text


def _resolve_vector_store_id(passed_vector_store_id: str) -> str:
    configured = getattr(settings, "OPENAI_VECTOR_STORE_ID", "").strip()
    if configured:
        return configured
    return (passed_vector_store_id or "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_turn(
    question: str,
    history: list,
    vector_store_id: str,
    language: str = "en",
) -> dict:
    """
    Run one conversation turn through the LLM (with RAG file_search).

    Returns
    -------
    {
        'answer'        : str,
        'transfer'      : bool,
        'reason'        : str,
        'closing'       : bool,
        'rag_no_answer' : bool,
        'follow_up'     : bool,
        'follow_up_type': str,
        'follow_up_note': str,
    }
    """
    language = _normalize_language(language)
    question = (question or "").strip()

    # 1) Rule-based closing
    if _rule_based_closing(question):
        from apps.portal.models import SiteConfig
        _company = SiteConfig.get_solo().company_name
        farewell = (
            f"Thank you for calling {_company}. Have a great day!"
            if language == "en"
            else f"شكرًا لاتصالك بـ {_company}. يومك سعيد!"
        )
        result = {
            "answer": farewell,
            "transfer": False,
            "reason": "",
            "closing": True,
            "rag_no_answer": False,
        }
        result.update(_build_follow_up(False, "", ""))
        return result

    # 2) Rule-based transfer
    transfer, reason = _rule_based_transfer(question)
    if transfer:
        handoff_note = (
            "I understand you'd like to speak with a team member. Please hold while I transfer you now."
            if language == "en"
            else "أفهم أنك ترغب في التحدث مع أحد أعضاء الفريق. يرجى الانتظار بينما أقوم بتحويلك الآن."
        )
        result = {
            "answer": handoff_note,
            "transfer": True,
            "reason": reason,
            "closing": False,
            "rag_no_answer": False,
        }
        result.update(_build_follow_up(True, "callback", f"Transfer requested: {reason}"))
        return result

    # 3) Rule-based business handling
    quick_reply, fu = _rule_based_business_reply(question, language=language)
    if quick_reply:
        result = {
            "answer": quick_reply,
            "transfer": False,
            "reason": "",
            "closing": False,
            "rag_no_answer": False,
        }
        result.update(fu)
        return result

    # 4) LLM call
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    messages = _build_messages(question, history, language=language)
    resolved_vector_store_id = _resolve_vector_store_id(vector_store_id)

    logger.debug(
        f"LLM request: question_len={len(question)} "
        f"history_turns={len(history)} lang={language}"
    )

    try:
        if resolved_vector_store_id:
            try:
                response = client.responses.create(
                    model=MODEL_NAME,
                    input=messages,
                    max_output_tokens=120 if language == "ar" else 160,
                    tools=[{
                        "type": "file_search",
                        "vector_store_ids": [resolved_vector_store_id],
                    }],
                )
                raw_reply = response.output_text.strip()
            except Exception as exc:
                logger.warning(
                    f"LLM RAG call failed, falling back to plain chat. "
                    f"vector_store_id={resolved_vector_store_id} | error={exc}"
                )
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=120 if language == "ar" else 160,
                    temperature=0.3,
                )
                raw_reply = completion.choices[0].message.content.strip()
        else:
            logger.warning("No OPENAI_VECTOR_STORE_ID available — using plain chat completion.")
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=120 if language == "ar" else 160,
                temperature=0.3,
            )
            raw_reply = completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}", exc_info=True)
        raise

    # 5) Parse tokens
    clean_reply, llm_transfer, llm_reason, closing, no_answer = _parse_llm_tokens(raw_reply)
    clean_reply = _clean_phone_reply(clean_reply, language=language)

    if llm_transfer:
        logger.info(f"Transfer flagged by LLM: {llm_reason}")
    if closing:
        logger.info("Closing detected by LLM token.")
    if no_answer:
        logger.info("RAG no-answer detected.")

    logger.debug(
        f"LLM reply: len={len(clean_reply)} transfer={llm_transfer} "
        f"closing={closing} no_answer={no_answer}"
    )

    # 6) Follow-up heuristics after LLM
    follow_up = False
    follow_up_type = ""
    follow_up_note = ""

    q_low = question.lower()

    if no_answer:
        follow_up = True
        follow_up_type = "inquiry"
        follow_up_note = "Caller asked something that may need human follow-up because the knowledge base did not answer confidently."
    elif llm_transfer:
        follow_up = True
        follow_up_type = "callback"
        follow_up_note = f"LLM requested transfer: {llm_reason}"
    elif any(word in q_low for word in ["price", "pricing", "cost", "package", "demo", "interested"]) or \
         any(word in question for word in ["السعر", "الأسعار", "الباقة", "الباقات", "مهتم", "عرض", "تفاصيل"]):
        follow_up = True
        follow_up_type = "lead"
        follow_up_note = "Potential customer asked about pricing, packages, or showed commercial interest."

    return {
        "answer": clean_reply,
        "transfer": llm_transfer,
        "reason": llm_reason,
        "closing": closing,
        "rag_no_answer": no_answer,
        "follow_up": follow_up,
        "follow_up_type": follow_up_type,
        "follow_up_note": follow_up_note,
    }
