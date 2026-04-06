"""
Knowledge retrieval service.

Public API:
    answer_question(question: str) -> str

Sends the question to OpenAI's Responses API with the file_search tool
pointed at the persistent vector store. Returns a clean text answer sourced
strictly from indexed company documents.

If no relevant content is found, returns the FALLBACK_RESPONSE string exactly.
This service is intentionally thin — all prompt engineering lives here so it
can be updated independently of the Celery pipeline and call-handling code.
"""
import logging

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Exact string returned when the model finds no relevant document content.
# Callers may check `answer == FALLBACK_RESPONSE` to detect a miss.
FALLBACK_RESPONSE = "No confirmed information found in company documents."

# System-level instruction sent with every retrieval request.
_SYSTEM_PROMPT = (
    "You are a company assistant. "
    "Answer ONLY using information found in the provided documents. "
    "If the answer is not in the documents, reply exactly with: "
    f'"{FALLBACK_RESPONSE}" '
    "Do not guess, infer, or use outside knowledge. "
    "Do not preface your answer with phrases like 'based on the documents'."
)


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _get_vector_store_id() -> str:
    """
    Return the configured vector store ID.
    Raises ImproperlyConfigured if OPENAI_VECTOR_STORE_ID is not set,
    so the error surfaces early (at request time) with a clear message.
    """
    from django.core.exceptions import ImproperlyConfigured

    vs_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', '').strip()
    if not vs_id:
        raise ImproperlyConfigured(
            "OPENAI_VECTOR_STORE_ID is not set in .env / Django settings. "
            "Upload at least one document via the admin, note the vector store "
            "ID from the Celery log, and add it to .env."
        )
    return vs_id


def _extract_text(response) -> str:
    """Pull plain text out of an OpenAI Responses API response object."""
    parts = []
    for output in response.output:
        # The Responses API returns output items; message items have .content
        if not hasattr(output, 'content'):
            continue
        for block in output.content:
            # Text blocks have a .text attribute (str on newer SDK versions)
            text = getattr(block, 'text', None)
            if text is None:
                continue
            # SDK may return a TextContent object with a .value field
            if hasattr(text, 'value'):
                parts.append(text.value)
            elif isinstance(text, str):
                parts.append(text)
    return ''.join(parts).strip()


def answer_question(question: str) -> str:
    """
    Ask a question against the company knowledge base.

    Args:
        question: Natural-language question from the user / caller.

    Returns:
        A text answer grounded in the indexed documents, or FALLBACK_RESPONSE
        if no relevant content was found.

    Raises:
        ImproperlyConfigured: if OPENAI_VECTOR_STORE_ID is not configured.
        openai.OpenAIError: on API-level failures (let the caller handle retry).
    """
    if not question or not question.strip():
        logger.warning("answer_question called with empty question — returning fallback.")
        return FALLBACK_RESPONSE

    vector_store_id = _get_vector_store_id()
    client = _get_client()

    logger.info(
        f"Retrieval query | vs={vector_store_id} | "
        f"question={question[:120]!r}"
    )

    response = client.responses.create(
        model='gpt-4o-mini',
        instructions=_SYSTEM_PROMPT,
        input=question.strip(),
        tools=[
            {
                'type': 'file_search',
                'vector_store_ids': [vector_store_id],
            }
        ],
    )

    answer = _extract_text(response)

    if not answer:
        logger.warning(
            "OpenAI returned an empty response for question: %r", question[:120]
        )
        return FALLBACK_RESPONSE

    logger.info(f"Retrieval answer ({len(answer)} chars): {answer[:120]!r}")
    return answer
