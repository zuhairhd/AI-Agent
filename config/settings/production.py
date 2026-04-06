from .base import *
import os

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
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs/app.log"),
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "INFO",
            "propagate": True,
        },
    },
}