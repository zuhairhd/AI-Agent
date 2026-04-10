"""
OpenAI Vector Store service.

Design: one persistent shared vector store for the entire knowledge base.

Behavior:
- If OPENAI_VECTOR_STORE_ID is set and valid   -> reuse it
- If OPENAI_VECTOR_STORE_ID is set but invalid -> create a new store automatically
- If OPENAI_VECTOR_STORE_ID is empty           -> create a new store automatically

IMPORTANT:
When a new vector store is created, its ID is logged clearly so the operator
can copy it into .env as OPENAI_VECTOR_STORE_ID=vs_xxxx and restart services.
"""

import logging
import time

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2    # seconds between indexing status checks
_MAX_POLLS = 150      # 150 × 2 s = 5 minutes maximum wait


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Vector store lifecycle
# ---------------------------------------------------------------------------

def _create_vector_store(name: str) -> str:
    """Create a new vector store and log its ID clearly."""
    client = _get_client()
    store = client.vector_stores.create(name=name)

    logger.warning(
        "=================================================================\n"
        "  NEW VECTOR STORE CREATED: %s\n"
        "  Add this to your .env:\n"
        "  OPENAI_VECTOR_STORE_ID=%s\n"
        "  Then restart Celery worker / beat / Gunicorn.\n"
        "=================================================================",
        store.id,
        store.id,
    )

    return store.id


def ensure_vector_store(name: str = "company_knowledge_base") -> str:
    """
    Return a usable persistent vector store ID.

    Reads OPENAI_VECTOR_STORE_ID from Django settings.

    Cases:
    - valid configured ID   -> reuse it
    - invalid configured ID -> create a new one automatically
    - missing configured ID -> create a new one automatically
    """
    client = _get_client()
    vector_store_id = getattr(settings, "OPENAI_VECTOR_STORE_ID", "").strip()

    if vector_store_id:
        try:
            client.vector_stores.retrieve(vector_store_id)
            logger.info(f"Reusing persistent vector store: {vector_store_id}")
            return vector_store_id
        except Exception as exc:
            logger.warning(
                "Configured OPENAI_VECTOR_STORE_ID is invalid or deleted: %s | %s",
                vector_store_id,
                exc,
            )
            logger.warning("Creating a replacement vector store automatically.")
            return _create_vector_store(name)

    logger.warning(
        "OPENAI_VECTOR_STORE_ID is not set. Creating a new vector store automatically."
    )
    return _create_vector_store(name)


# ---------------------------------------------------------------------------
# File attachment and indexing
# ---------------------------------------------------------------------------

def attach_file(vector_store_id: str, file_id: str) -> None:
    """Attach an already-uploaded OpenAI file to the vector store."""
    client = _get_client()
    logger.info(f"Attaching file {file_id} to vector store {vector_store_id}")
    client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id,
    )
    logger.info(f"File attached: {file_id}")


def check_status(vector_store_id: str, file_id: str) -> str:
    """
    Poll until the file is indexed in the vector store.

    Returns one of: 'completed' | 'failed' | 'timeout'
    """
    client = _get_client()
    logger.info(
        f"Polling indexing status for file {file_id} "
        f"in store {vector_store_id}"
    )

    for attempt in range(_MAX_POLLS):
        file_status = client.vector_stores.files.retrieve(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )
        status = file_status.status
        logger.debug(f"Poll {attempt + 1}: status={status}")

        if status == "completed":
            logger.info(f"File {file_id} indexed successfully.")
            return "completed"

        if status == "failed":
            logger.error(f"File {file_id} indexing failed.")
            return "failed"

        time.sleep(_POLL_INTERVAL)

    logger.error(f"Timed out waiting for file {file_id} to index.")
    return "timeout"
