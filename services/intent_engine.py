"""
Intent detection engine for voice calls.

Purpose
-------
Fast, rule-based intent detection before LLM.
This reduces bad answers, repetition, awkward phone behavior,
and helps the system react quickly to common sales/support intents.

Output example
--------------
{
    "intent": "office_visit",
    "confidence": 0.92,
    "entities": {},
    "closing": False,
    "transfer": False,
    "follow_up": True,
    "follow_up_type": "office_visit",
}
"""

from __future__ import annotations

import re
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Cleanup / normalization
# ---------------------------------------------------------------------------

STOP_WORDS = [
    "من فضلك",
    "لحظة",
    "انتظر",
    "please",
    "kindly",
]


def clean_text(text: str) -> str:
    """
    Remove filler words that should not affect intent detection.
    """
    text = text or ""
    for word in STOP_WORDS:
        text = text.replace(word, "")
    return " ".join(text.split()).strip()


def normalize_language(language: str | None) -> str:
    language = (language or "en").strip().lower()
    return "ar" if language.startswith("ar") else "en"


# ---------------------------------------------------------------------------
# Pattern dictionaries
# ---------------------------------------------------------------------------

AR_CLOSING = [
    r"مع\s*السلامة",
    r"شكراً?",
    r"اشكرك",
    r"أشكرك",
    r"في\s*أمان\s*الله",
    r"خلاص",
    r"انتهينا",
    r"ما\s*قصرت",
    r"يعطيك\s*العافية",
    r"السلام\s*عليكم",
    r"نشكركم",
    r"شكركم",
]

EN_CLOSING = [
    r"\bbye\b",
    r"\bgoodbye\b",
    r"\bthank you\b",
    r"\bthanks\b",
    r"\bthat'?s all\b",
    r"\bno more questions\b",
    r"\bi'?m done\b",
    r"\bsee you\b",
]

AR_OFFICE_VISIT = [
    r"زيارة\s*المكتب",
    r"أزور\s*المكتب",
    r"آتي\s*إلى\s*المكتب",
    r"أجي\s*المكتب",
    r"يجي\s*عندي",
    r"يزورني",
    r"زيارة",
    r"ممكن\s*أجي",
    r"ممكن\s*تزورني",
]

EN_OFFICE_VISIT = [
    r"\bvisit\b.*\boffice\b",
    r"\bcome to your office\b",
    r"\bvisit your office\b",
    r"\bcome to the office\b",
    r"\bvisit the office\b",
]

AR_PRODUCT = [
    r"ما\s*هو\s*المنتج",
    r"ما\s*هو\s*منتجكم",
    r"ما\s*هي\s*خدماتكم",
    r"ما\s*الذي\s*تقدمونه",
    r"أريد\s*معرفة\s*المنتج",
    r"عرفني\s*على\s*الخدمة",
    r"ما\s*الخدمة",
    r"وش\s*الخدمة",
    r"وش\s*منتجكم",
]

EN_PRODUCT = [
    r"\bwhat is your product\b",
    r"\babout your product\b",
    r"\bwhat do you offer\b",
    r"\bwhat is voicegate\b",
    r"\bwhat is your service\b",
]

AR_PRICE = [
    r"السعر",
    r"الأسعار",
    r"كم",
    r"التكلفة",
    r"بكم",
    r"سعرها",
    r"سعره",
]

EN_PRICE = [
    r"\bprice\b",
    r"\bpricing\b",
    r"\bcost\b",
    r"\bhow much\b",
]

AR_BEST_PACKAGE = [
    r"أي\s*باقة\s*أفضل",
    r"ما\s*الباقة\s*المناسبة",
    r"ما\s*الباقة\s*التي\s*تنصحون\s*بها",
    r"وين\s*أفضل\s*باقة",
    r"أفضل\s*باقة",
    r"أنسب\s*باقة",
]

EN_BEST_PACKAGE = [
    r"\bwhich package is best\b",
    r"\bwhat package do you recommend\b",
    r"\bbest package\b",
    r"\brecommended package\b",
]

AR_INTEREST = [
    r"مهتم",
    r"أريد\s*تفاصيل",
    r"أريد\s*عرض",
    r"تواصلوا\s*معي",
    r"اتصلوا\s*بي",
    r"أريد\s*تجربة",
    r"أريد\s*متابعة",
    r"أريد\s*أحد\s*يتواصل",
]

EN_INTEREST = [
    r"\bi'?m interested\b",
    r"\binterested\b",
    r"\bcontact me\b",
    r"\bcall me\b",
    r"\bdemo\b",
    r"\bfollow up\b",
]

AR_CONFUSION = [
    r"لم\s*أفهم",
    r"ما\s*فهمت",
    r"ماذا\s*تقصد",
    r"وضح",
    r"فسر",
    r"بشكل\s*أوضح",
    r"أعد",
    r"ما\s*فهمت\s*عليك",
]

EN_CONFUSION = [
    r"\bi don'?t understand\b",
    r"\bcan you explain\b",
    r"\bi did not understand\b",
    r"\bwhat do you mean\b",
]

AR_TRANSFER = [
    r"أريد\s*موظف",
    r"أريد\s*شخص",
    r"حولني",
    r"أكلم\s*الموظف",
    r"المدير",
    r"المشرف",
    r"شخص\s*حقيقي",
]

EN_TRANSFER = [
    r"\bspeak to (a )?(human|person|agent|representative)\b",
    r"\btransfer me\b",
    r"\bconnect me\b",
    r"\bmanager\b",
    r"\bsupervisor\b",
    r"\breal person\b",
]

AR_PACKAGE_BASIC = [r"الأساسية"]
AR_PACKAGE_STANDARD = [r"القياسية"]
AR_PACKAGE_PREMIUM = [r"المتقدمة"]

EN_PACKAGE_BASIC = [r"\bbasic\b"]
EN_PACKAGE_STANDARD = [r"\bstandard\b"]
EN_PACKAGE_PREMIUM = [r"\bpremium\b"]


def _compile_list(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns]


RX = {
    "closing_ar": _compile_list(AR_CLOSING),
    "closing_en": _compile_list(EN_CLOSING),
    "office_ar": _compile_list(AR_OFFICE_VISIT),
    "office_en": _compile_list(EN_OFFICE_VISIT),
    "product_ar": _compile_list(AR_PRODUCT),
    "product_en": _compile_list(EN_PRODUCT),
    "price_ar": _compile_list(AR_PRICE),
    "price_en": _compile_list(EN_PRICE),
    "best_ar": _compile_list(AR_BEST_PACKAGE),
    "best_en": _compile_list(EN_BEST_PACKAGE),
    "interest_ar": _compile_list(AR_INTEREST),
    "interest_en": _compile_list(EN_INTEREST),
    "confusion_ar": _compile_list(AR_CONFUSION),
    "confusion_en": _compile_list(EN_CONFUSION),
    "transfer_ar": _compile_list(AR_TRANSFER),
    "transfer_en": _compile_list(EN_TRANSFER),
    "basic_ar": _compile_list(AR_PACKAGE_BASIC),
    "standard_ar": _compile_list(AR_PACKAGE_STANDARD),
    "premium_ar": _compile_list(AR_PACKAGE_PREMIUM),
    "basic_en": _compile_list(EN_PACKAGE_BASIC),
    "standard_en": _compile_list(EN_PACKAGE_STANDARD),
    "premium_en": _compile_list(EN_PACKAGE_PREMIUM),
}


def _matches(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def detect_intent(text: str, language: str = "en") -> Dict[str, Any]:
    """
    Detect business intent quickly before calling the LLM.
    """
    lang = normalize_language(language)
    text = clean_text((text or "").strip())

    if not text:
        return {
            "intent": "empty",
            "confidence": 0.0,
            "entities": {},
            "closing": False,
            "transfer": False,
            "follow_up": False,
            "follow_up_type": "",
        }

    suffix = "ar" if lang == "ar" else "en"

    if _matches(text, RX[f"closing_{suffix}"]):
        return {
            "intent": "closing",
            "confidence": 0.99,
            "entities": {},
            "closing": True,
            "transfer": False,
            "follow_up": False,
            "follow_up_type": "",
        }

    if _matches(text, RX[f"transfer_{suffix}"]):
        return {
            "intent": "human_transfer",
            "confidence": 0.98,
            "entities": {},
            "closing": False,
            "transfer": True,
            "follow_up": True,
            "follow_up_type": "callback",
        }

    if _matches(text, RX[f"office_{suffix}"]):
        return {
            "intent": "office_visit",
            "confidence": 0.94,
            "entities": {},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "office_visit",
        }

    if _matches(text, RX[f"product_{suffix}"]):
        return {
            "intent": "product_info",
            "confidence": 0.92,
            "entities": {},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "inquiry",
        }

    if _matches(text, RX[f"best_{suffix}"]):
        return {
            "intent": "best_package",
            "confidence": 0.95,
            "entities": {"recommended": "standard"},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "pricing",
        }

    if _matches(text, RX[f"price_{suffix}"]):
        return {
            "intent": "pricing",
            "confidence": 0.90,
            "entities": {},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "pricing",
        }

    if _matches(text, RX[f"interest_{suffix}"]):
        return {
            "intent": "lead_interest",
            "confidence": 0.91,
            "entities": {},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "lead",
        }

    if _matches(text, RX[f"confusion_{suffix}"]):
        return {
            "intent": "clarification",
            "confidence": 0.89,
            "entities": {},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "inquiry",
        }

    package = None
    if _matches(text, RX[f"basic_{suffix}"]):
        package = "basic"
    elif _matches(text, RX[f"standard_{suffix}"]):
        package = "standard"
    elif _matches(text, RX[f"premium_{suffix}"]):
        package = "premium"

    if package:
        return {
            "intent": "package_details",
            "confidence": 0.90,
            "entities": {"package": package},
            "closing": False,
            "transfer": False,
            "follow_up": True,
            "follow_up_type": "pricing",
        }

    return {
        "intent": "general",
        "confidence": 0.50,
        "entities": {},
        "closing": False,
        "transfer": False,
        "follow_up": False,
        "follow_up_type": "",
    }
