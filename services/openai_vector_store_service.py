"""
OpenAI Vector Store service.

Design: one persistent shared vector store for the entire knowledge base.

The store ID is read from settings.OPENAI_VECTOR_STORE_ID (env: OPENAI_VECTOR_STORE_ID).

- If the ID is set   → reuse it; never create a new store.
- If the ID is empty → create one store, log its ID prominently, and raise
                       an error to force the operator to persist the ID in .env.
                       This prevents silent proliferation of orphan stores.
"""
import logging
import time

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2   # seconds between indexing status checks
_MAX_POLLS     = 150  # 150 × 2 s = 5 minutes maximum wait


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Vector store lifecycle
# ---------------------------------------------------------------------------

def ensure_vector_store(name: str = 'company_knowledge_base') -> str:
    """
    Return the persistent vector store ID.

    Reads OPENAI_VECTOR_STORE_ID from Django settings (populated via .env).
    If not set, creates one new store, logs the ID at WARNING level so the
    operator can copy it into .env, then raises RuntimeError to prevent silent
    data scattering across multiple stores.

    On a freshly configured system the operator should:
      1. Run once — the ID is printed to the logs.
      2. Copy the ID into .env as OPENAI_VECTOR_STORE_ID=vs_xxxx
      3. Restart the worker — all subsequent uploads reuse that store.
    """
    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', '').strip()

    if vector_store_id:
        logger.info(f"Reusing persistent vector store: {vector_store_id}")
        return vector_store_id

    # No ID configured — create once and force the operator to persist it.
    client = _get_client()
    logger.warning(
        "OPENAI_VECTOR_STORE_ID is not set. "
        "Creating a new vector store. Copy the ID below into your .env file."
    )
    store = client.vector_stores.create(name=name)
    logger.warning(
        "=================================================================\n"
        f"  NEW VECTOR STORE CREATED: {store.id}\n"
        "  Add this to your .env:  OPENAI_VECTOR_STORE_ID=%s\n"
        "  Then restart the Celery worker and Gunicorn.\n"
        "=================================================================",
        store.id,
    )
    # Raise so the Celery task fails loudly instead of creating a new store
    # on every document upload.
    raise RuntimeError(
        f"OPENAI_VECTOR_STORE_ID not set. "
        f"A new vector store was created: {store.id}. "
        f"Set OPENAI_VECTOR_STORE_ID={store.id} in .env and restart services."
    )


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

        if status == 'completed':
            logger.info(f"File {file_id} indexed successfully.")
            return 'completed'
        if status == 'failed':
            logger.error(f"File {file_id} indexing failed.")
            return 'failed'

        time.sleep(_POLL_INTERVAL)

    logger.error(f"Timed out waiting for file {file_id} to index.")
    return 'timeout'
