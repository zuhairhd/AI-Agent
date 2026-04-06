import logging
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a company assistant. Answer ONLY using the provided documents.
If the answer is not found in the documents, reply exactly:
"No confirmed information found in company documents."
Never guess, infer, or use outside knowledge. Do not say things like "based on the documents" — just answer directly."""

FALLBACK_RESPONSE = "No confirmed information found in company documents."


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def query_rag(question: str, vector_store_id: str) -> str:
    """
    Query the OpenAI Responses API using file_search against the vector store.
    Returns the assistant's answer, strictly from company documents.
    """
    client = _get_client()

    logger.info(f"Querying RAG for question: {question[:100]}...")

    response = client.responses.create(
        model='gpt-4o-mini',
        instructions=SYSTEM_PROMPT,
        input=question,
        tools=[
            {
                'type': 'file_search',
                'vector_store_ids': [vector_store_id],
            }
        ],
    )

    # Extract text from response
    answer = ''
    for output in response.output:
        if hasattr(output, 'content'):
            for content_block in output.content:
                if hasattr(content_block, 'text'):
                    answer += content_block.text

    answer = answer.strip()
    if not answer:
        logger.warning("Empty response from OpenAI — returning fallback.")
        return FALLBACK_RESPONSE

    logger.info(f"RAG response received ({len(answer)} chars)")
    return answer
