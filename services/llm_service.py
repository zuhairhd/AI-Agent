"""
LLM service for multi-turn voice agent.

Public API
----------
process_turn(question: str, history: list[dict], vector_store_id: str)
    -> dict with keys:
        answer   : str   — the assistant reply text
        transfer : bool  — True if a human handoff should be triggered
        reason   : str   — human-readable reason for transfer (or '')

Hybrid transfer detection
-------------------------
1. Rule-based checks run FIRST on the raw caller text (fast, no extra API cost).
2. If no rule fires, the LLM reply is parsed for a structured transfer flag.
   The system prompt asks the model to append [TRANSFER] if handoff is needed.
"""

import logging
import re

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are the virtual assistant for {company}. "
    "You speak professionally, clearly, and briefly — you are on a phone call. "
    "Help callers with support-related requests. "
    "Answer only from the company knowledge base when possible. "
    "If the user explicitly asks for a human agent, expresses frustration, "
    "requests something you cannot handle safely or confidently, has a billing "
    "dispute, or has an urgent complaint, append the exact token [TRANSFER] on "
    "its own line at the very end of your reply and briefly state the reason "
    "after a colon, e.g.:\n"
    "[TRANSFER]: user requested human agent\n\n"
    "Otherwise do NOT include [TRANSFER]. Keep replies short and phone-friendly."
)

# Language-specific instructions injected after the base system prompt.
_LANGUAGE_INSTRUCTION: dict[str, str] = {
    'ar': (
        "IMPORTANT: You MUST respond ONLY in Arabic (العربية). "
        "Do not use any English words at all. "
        "Do not mix languages under any circumstances."
    ),
    'en': '',  # no extra instruction needed for English
}

# Rule-based transfer keywords/patterns (checked against caller utterance)
_TRANSFER_PATTERNS: list[tuple[str, str]] = [
    (r'\b(speak|talk)\s+(to\s+)?(a\s+)?(human|person|agent|representative|staff|operator)\b',
     'explicit_request:human'),
    (r'\b(transfer|connect)\s+me\b', 'explicit_request:transfer'),
    (r'\b(manager|supervisor)\b', 'explicit_request:supervisor'),
    (r'\b(this\s+is\s+)?urgent\b', 'urgency:urgent'),
    (r'\b(billing\s+dispute|charge\s+dispute|wrong\s+charge)\b', 'billing_dispute'),
    # Explicit grouping so alternation does not leak outside the \b boundary
    (r'\b(very\s+)?(angry|furious|frustrated|unacceptable)\b', 'frustration:angry'),
    # Literal apostrophe — do NOT use . here (it would match any char)
    (r"\byou're\s+(useless|stupid|not\s+helpful)\b", 'frustration:insult'),
]

_TRANSFER_RE = [(re.compile(p, re.I), reason) for p, reason in _TRANSFER_PATTERNS]

# Sentinel the model appends when it decides to transfer
_LLM_TRANSFER_TOKEN = '[TRANSFER]'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_messages(question: str, history: list[dict], language: str = 'en') -> list[dict]:
    """
    Assemble the message list for the LLM call.
    history: list of {'role': 'user'|'assistant', 'content': str}
    language: 'en' or 'ar' — injects strict language instruction when Arabic.
    vector_store_id is NOT used here; it is passed directly to the API tool config.
    """
    company = getattr(settings, 'COMPANY_NAME', 'Future Smart Support')
    system_content = SYSTEM_PROMPT.format(company=company)

    lang_instr = _LANGUAGE_INSTRUCTION.get(language, '')
    if lang_instr:
        system_content = f"{system_content}\n\n{lang_instr}"

    messages = [{'role': 'system', 'content': system_content}]
    messages.extend(history[-10:])  # cap context at last 10 turns to save tokens
    messages.append({'role': 'user', 'content': question})
    return messages


def _rule_based_transfer(caller_text: str) -> tuple[bool, str]:
    """
    Check caller text against keyword rules.
    Returns (transfer_needed, reason).
    """
    for pattern, reason in _TRANSFER_RE:
        if pattern.search(caller_text):
            logger.info(f"Rule-based transfer triggered: {reason!r}")
            return True, reason
    return False, ''


def _parse_llm_transfer(reply: str) -> tuple[str, bool, str]:
    """
    Strip [TRANSFER]: reason from the end of the LLM reply if present.
    Returns (clean_reply, transfer_needed, reason).
    """
    lines = reply.strip().splitlines()
    if lines and lines[-1].startswith(_LLM_TRANSFER_TOKEN):
        # e.g. "[TRANSFER]: user requested human agent"
        token_line = lines[-1]
        reason = token_line[len(_LLM_TRANSFER_TOKEN):].lstrip(':').strip()
        clean = '\n'.join(lines[:-1]).strip()
        return clean, True, f'llm_flag:{reason}'
    return reply, False, ''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_turn(
    question: str,
    history: list[dict],
    vector_store_id: str,
    language: str = 'en',
) -> dict:
    """
    Run one conversation turn through the LLM (with RAG file_search).

    Parameters
    ----------
    question         : caller's current utterance (already transcribed)
    history          : previous turns as [{'role': ..., 'content': ...}]
    vector_store_id  : OpenAI vector store to search
    language         : 'en' or 'ar' — controls response language

    Returns
    -------
    {
        'answer'   : str,
        'transfer' : bool,
        'reason'   : str,   # empty if no transfer
    }
    """
    # ── 1. Rule-based transfer check (fast path, no API cost) ──────────────
    transfer, reason = _rule_based_transfer(question)
    if transfer:
        logger.info(f"Transfer flagged by rule before LLM call: {reason}")
        handoff_note = (
            "I understand you'd like to speak with a team member. "
            "Please hold while I transfer you now."
            if language == 'en'
            else
            "سأقوم بتحويلك الآن إلى أحد أعضاء الفريق، يرجى الانتظار."
        )
        return {'answer': handoff_note, 'transfer': True, 'reason': reason}

    # ── 2. LLM call with file_search (RAG) ────────────────────────────────
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    messages = _build_messages(question, history, language=language)

    logger.debug(f"LLM request: question_len={len(question)} history_turns={len(history)} lang={language}")

    try:
        if vector_store_id:
            # OpenAI Responses API (sdk >= 1.x).
            # `input` accepts a list of message dicts with role/content.
            # `tools` carries the file_search tool configuration.
            response = client.responses.create(
                model='gpt-4o-mini',
                input=messages,
                tools=[{
                    'type': 'file_search',
                    'vector_store_ids': [vector_store_id],
                }],
            )
            # response.output_text is the text of the first output message item.
            raw_reply = response.output_text.strip()
        else:
            # Fallback: plain Chat Completions when no vector store is configured.
            logger.warning("No OPENAI_VECTOR_STORE_ID — using plain chat completion.")
            completion = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages,
                max_tokens=300,
                temperature=0.4,
            )
            raw_reply = completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}", exc_info=True)
        raise

    # ── 3. Parse LLM transfer token from reply ────────────────────────────
    clean_reply, llm_transfer, llm_reason = _parse_llm_transfer(raw_reply)

    if llm_transfer:
        logger.info(f"Transfer flagged by LLM: {llm_reason}")

    logger.debug(f"LLM reply: len={len(clean_reply)} transfer={llm_transfer}")

    return {
        'answer':   clean_reply,
        'transfer': llm_transfer,
        'reason':   llm_reason,
    }
