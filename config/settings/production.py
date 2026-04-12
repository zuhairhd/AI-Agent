from .base import *
import os

# Email (Gmail SMTP)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"Future Smart Support <{EMAIL_HOST_USER}>"
)

#EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
#EMAIL_HOST = "smtp.gmail.com"
#EMAIL_PORT = 587
#EMAIL_USE_TLS = True

#EMAIL_HOST_USER = "zuhairhd@gmail.com"
#EMAIL_HOST_PASSWORD = "ryjftibdagwjarsi"

#DEFAULT_FROM_EMAIL = "Future Smart Support <zuhairhd@gmail.com>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL


# 🔓 Basic
DEBUG = False
ALLOWED_HOSTS = ["*"]

# ⚠️ مهم: لا تفرض HTTPS إذا لم تستخدمه فعليًا
# لأن هذا سيسبب مشاكل في login و CSRF
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookies (خليها False في الشبكة الداخلية بدون SSL)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Headers (آمنة ولا تسبب مشاكل)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ❌ لا تفرض HSTS بدون SSL (يسبب مشاكل)
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# 🧱 Static & Media
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# 🧠 مهم مع Nginx
USE_X_FORWARDED_HOST = True

# 🧾 Logging
# Captures: Django, all app loggers (apps.portal.*, tasks.*), and Celery.
# Without explicit entries here, app-level logger.info() calls are silently
# discarded in production — making email delivery failures invisible.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs/app.log"),
            "formatter": "verbose",
        },
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        # Django internals
        "django": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
        # Portal app — signals, tasks, email_service
        "apps.portal": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Celery periodic/SLA tasks
        "tasks": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # Voice-call processing
        "apps.voice_calls": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
        # Catch-all for any other app loggers
        "": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": True,
        },
    },
}
