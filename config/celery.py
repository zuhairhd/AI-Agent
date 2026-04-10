import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('voice_ai_agent')
app.config_from_object('django.conf:settings', namespace='CELERY')
# Use Django's INSTALLED_APPS to discover tasks automatically.
# This finds tasks.py (or tasks/ packages) inside every installed app,
# including 'apps.rag_sync', 'apps.voice_calls', etc.
# The top-level 'tasks' package is also included explicitly as a fallback
# because call_tasks.py and sync_tasks.py live there directly.
app.autodiscover_tasks()
app.autodiscover_tasks(['tasks'])  # top-level tasks/ package (call_tasks, sync_tasks)

# ✅ ADD HERE (after config is ready)
# import tasks.sync_tasks

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
