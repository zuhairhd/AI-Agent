# Explicitly import task sub-modules so Celery registers them when it loads
# this package via autodiscover_tasks(['tasks']).
#
# Without these imports, autodiscover_tasks only loads tasks/__init__.py and
# never sees sync_tasks.py or call_tasks.py, causing
# "Received unregistered task of type 'tasks.sync_document'" at runtime.
from tasks.sync_tasks import sync_document    # noqa: F401  registers tasks.sync_document
from tasks.call_tasks import process_call     # noqa: F401  registers tasks.process_call
from tasks.process_turn import process_turn   # noqa: F401  registers tasks.process_turn

__all__ = ['sync_document', 'process_call', 'process_turn']
