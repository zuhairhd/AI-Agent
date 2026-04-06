from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.portal'
    verbose_name = 'FSS Admin Portal'

    def ready(self):
        import apps.portal.signals  # noqa: F401 — connects post_save handlers
