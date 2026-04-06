# Expose the Celery app instance so that Django's manage.py and
# any code doing `from config import celery_app` can import it.
# This is the standard Django + Celery wiring pattern.
from .celery import app as celery_app

__all__ = ('celery_app',)
