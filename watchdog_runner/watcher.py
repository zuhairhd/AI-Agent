"""
Standalone watchdog process to monitor /company_docs/ and trigger
Celery document sync tasks on file creation or modification.

Run as: python watchdog_runner/watcher.py
Or as a systemd service.
"""
import logging
import os
import sys
import time

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from django.conf import settings
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger('watchdog_runner')

SUPPORTED_EXTENSIONS = {'.txt', '.pdf', '.docx', '.md', '.csv', '.json'}


class DocumentSyncHandler(FileSystemEventHandler):
    """Handle filesystem events for the company_docs folder."""

    def _should_sync(self, path: str) -> bool:
        _, ext = os.path.splitext(path)
        return ext.lower() in SUPPORTED_EXTENSIONS

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_sync(event.src_path):
            logger.info(f"New file detected: {event.src_path}")
            self._dispatch(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_sync(event.src_path):
            logger.info(f"File modified: {event.src_path}")
            self._dispatch(event.src_path)

    def _dispatch(self, file_path: str):
        try:
            from tasks.sync_tasks import sync_document
            sync_document.delay(file_path)
            logger.info(f"Dispatched sync task for: {file_path}")
        except Exception as e:
            logger.error(f"Failed to dispatch sync task for {file_path}: {e}", exc_info=True)


def main():
    watch_dir = settings.COMPANY_DOCS_ROOT

    if not os.path.exists(watch_dir):
        os.makedirs(watch_dir, exist_ok=True)
        logger.info(f"Created watch directory: {watch_dir}")

    logger.info(f"Starting watchdog on: {watch_dir}")

    handler = DocumentSyncHandler()
    observer = Observer()
    observer.schedule(handler, path=watch_dir, recursive=True)
    observer.start()

    logger.info("Watchdog observer started. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
            if not observer.is_alive():
                logger.error("Observer died unexpectedly. Restarting...")
                observer.join()
                observer = Observer()
                observer.schedule(handler, path=watch_dir, recursive=True)
                observer.start()
    except KeyboardInterrupt:
        logger.info("Shutting down watchdog...")
        observer.stop()
    observer.join()
    logger.info("Watchdog stopped.")


if __name__ == '__main__':
    main()
