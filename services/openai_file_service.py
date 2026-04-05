import logging
import os
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def upload_file(file_path: str) -> str:
    """Upload a file to OpenAI Files API. Returns the openai_file_id."""
    client = _get_client()
    logger.info(f"Uploading file to OpenAI: {file_path}")
    with open(file_path, 'rb') as f:
        response = client.files.create(file=f, purpose='assistants')
    logger.info(f"File uploaded successfully: {response.id}")
    return response.id


def delete_file(openai_file_id: str) -> bool:
    """Delete a file from OpenAI Files API. Returns True on success."""
    client = _get_client()
    logger.info(f"Deleting OpenAI file: {openai_file_id}")
    try:
        client.files.delete(openai_file_id)
        logger.info(f"File deleted: {openai_file_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete file {openai_file_id}: {e}")
        return False
