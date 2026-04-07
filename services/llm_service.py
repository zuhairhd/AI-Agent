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

Hybrid transfer detection
-------------------------
1. Rule-based checks run FIRST on the raw caller text (fast, no extra API cost).
2. If no rule fires, the LLM reply is parsed for structured tokens:
   [TRANSFER] — handoff needed
   [CLOSING]  — caller said goodbye; terminate politely
   [NO_ANSWER]— RAG found nothing useful
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
    "If the knowledge base has no relevant information, append [NO_ANSWER] on its own line at the end. "
    "If the user explicitly asks for a human agent, expresses frustration, "
    "requests something you cannot handle safely or confidently, has a billing "
    "dispute, or has an urgent complaint, append [TRANSFER]: <reason> on its own line. "
    "If the caller says goodbye, thank you, or clearly ends the conversation, "
    "respond warmly and append [CLOSING] on its own line. "
    "Otherwise do NOT include any of these tokens. Keep replies short and phone-friendly."
)

_LANGUAGE_INSTRUCTION: dict = {
    'ar': (
        "IMPORTANT: You MUST respond ONLY in Arabic (العربية). "
        "Do not use any English words at all. "
        "Do not mix languages under any circumstances."
    ),
    'en': '',
}

# Closing phrases — detected rule-based before LLM call
_CLOSING_PATTERNS = [
    r'\b(thank\s+you|thanks|goodbye|good\s*bye|bye|see\s+you|that\'?s\s+all|no\s+more\s+questions?|i\'?m\s+done)\b',
    r'\bشكراً?\b',
    r'\bمع\s+السلامة\b',
    r'\bوداعاً?\b',
]
_CLOSING_RE = [re.compile(p, re.I) for p in _CLOSING_PATTERNS]

# Transfer keyword patterns
_TRANSFER_PATTERNS = [
    (r'\b(speak|talk)\s+(to\s+)?(a\s+)?(human|person|agent|representative|staff|operator)\b',
     'explicit_request:human'),
    (r'\b(transfer|connect)\s+me\b', 'explicit_request:transfer'),
    (r'\b(manager|supervisor)\b', 'explicit_request:supervisor'),
    (r'\b(this\s+is\s+)?urgent\b', 'urgency:urgent'),
    (r'\b(billing\s+dispute|charge\s+dispute|wrong\s+charge)\b', 'billing_dispute'),
    (r'\b(very\s+)?(angry|furious|frustrated|unacceptable)\b', 'frustration:angry'),
    (r"\byou're\s+(useless|stupid|not\s+helpful)\b", 'frustration:insult'),
]
_TRANSFER_RE = [(re.compile(p, re.I), reason) for p, reason in _TRANSFER_PATTERNS]

_LLM_TRANSFER_TOKEN  = '[TRANSFER]'
_LLM_CLOSING_TOKEN   = '[CLOSING]'
_LLM_NO_ANSWER_TOKEN = '[NO_ANSWER]'

# Phrases the model uses when RAG has no answer (rule-based check as backup)
_NO_ANSWER_PHRASES = [
    "no confirmed information",
    "not find any information",
    "cannot find",
    "no relevant",
    "not in the knowledge base",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_messages(question: str, history: list, language: str = 'en') -> list:
    company = getattr(settings, 'COMPANY_NAME', 'Future Smart Support')
    system_content = SYSTEM_PROMPT.format(company=company)

    lang_instr = _LANGUAGE_INSTRUCTION.get(language, '')
    if lang_instr:
        system_content = f"{system_content}\n\n{lang_instr}"

    messages = [{'role': 'system', 'content': system_content}]
    messages.extend(history[-10:])
    messages.append({'role': 'user', 'content': question})
    return messages


def _rule_based_transfer(caller_text: str) -> tuple:
    for pattern, reason in _TRANSFER_RE:
        if pattern.search(caller_text):
            logger.info(f"Rule-based transfer triggered: {reason!r}")
            return True, reason
    return False, ''


def _rule_based_closing(caller_text: str) -> bool:
    for pattern in _CLOSING_RE:
        if pattern.search(caller_text):
            logger.info("Rule-based closing phrase detected.")
            return True
    return False


def _parse_llm_tokens(reply: str) -> tuple:
    """
    Strip special LLM tokens from reply.
    Returns (clean_reply, transfer, transfer_reason, closing, no_answer).
    """
    lines = reply.strip().splitlines()
    transfer = False
    transfer_reason = ''
    closing = False
    no_answer = False
    clean_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_LLM_TRANSFER_TOKEN):
            transfer = True
            transfer_reason = stripped[len(_LLM_TRANSFER_TOKEN):].lstrip(':').strip()
            transfer_reason = f'llm_flag:{transfer_reason}' if transfer_reason else 'llm_flag'
        elif stripped == _LLM_CLOSING_TOKEN:
            closing = True
        elif stripped == _LLM_NO_ANSWER_TOKEN:
            no_answer = True
        else:
            clean_lines.append(line)

    clean = '\n'.join(clean_lines).strip()

    # Backup: detect no-answer from text heuristic
    if not no_answer and clean:
        low = clean.lower()
        if any(phrase in low for phrase in _NO_ANSWER_PHRASES):
            no_answer = True

    return clean, transfer, transfer_reason, closing, no_answer


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_turn(
    question: str,
    history: list,
    vector_store_id: str,
    language: str = 'en',
) -> dict:
    """
    Run one conversation turn through the LLM (with RAG file_search).

    Returns
    -------
    {
        'answer'        : str,
        'transfer'      : bool,
        'reason'        : str,
        'closing'       : bool,   # caller ended the conversation
        'rag_no_answer' : bool,   # RAG could not find relevant info
    }
    """
    # ── 1. Rule-based closing (fast exit) ─────────────────────────────────
    if _rule_based_closing(question):
        farewell = (
            "Thank you for calling Future Smart Support. Have a great day!"
            if language == 'en'
            else "شكراً لاتصالك بـ Future Smart Support. أتمنى لك يوماً رائعاً!"
        )
        return {
            'answer':        farewell,
            'transfer':      False,
            'reason':        '',
            'closing':       True,
            'rag_no_answer': False,
        }

    # ── 2. Rule-based transfer (fast exit) ─────────────────────────────────
    transfer, reason = _rule_based_transfer(question)
    if transfer:
        handoff_note = (
            "I understand you'd like to speak with a team member. "
            "Please hold while I transfer you now."
            if language == 'en'
            else
            "سأقوم بتحويلك الآن إلى أحد أعضاء الفريق، يرجى الانتظار."
        )
        return {
            'answer':        handoff_note,
            'transfer':      True,
            'reason':        reason,
            'closing':       False,
            'rag_no_answer': False,
        }

    # ── 3. LLM call with file_search (RAG) ────────────────────────────────
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    messages = _build_messages(question, history, language=language)

    logger.debug(
        f"LLM request: question_len={len(question)} "
        f"history_turns={len(history)} lang={language}"
    )

    try:
        if vector_store_id:
            response = client.responses.create(
                model='gpt-4o-mini',
                input=messages,
                tools=[{
                    'type': 'file_search',
                    'vector_store_ids': [vector_store_id],
                }],
            )
            raw_reply = response.output_text.strip()
        else:
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

    # ── 4. Parse tokens ─────────────────────────────────────────────────────
    clean_reply, llm_transfer, llm_reason, closing, no_answer = _parse_llm_tokens(raw_reply)

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

    return {
        'answer':        clean_reply,
        'transfer':      llm_transfer,
        'reason':        llm_reason,
        'closing':       closing,
        'rag_no_answer': no_answer,
    }
