import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'insecure-default-key')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_results',
    'rest_framework',
    'corsheaders',
    'apps.core',
    'apps.voice_calls',
    'apps.rag_sync',
    'apps.asterisk_bridge',
    'apps.admin_panel',
    'apps.portal',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'voice_ai_db'),
        'USER': os.environ.get('DB_USER', 'voice_ai_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
_frontend_dist = BASE_DIR / 'frontend' / 'dist'
STATICFILES_DIRS = [BASE_DIR / 'static'] + (
    [('portal', _frontend_dist)] if _frontend_dist.exists() else []
)

MEDIA_URL = '/media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media' / 'calls'))

COMPANY_DOCS_ROOT = os.environ.get('COMPANY_DOCS_ROOT', str(BASE_DIR / 'company_docs'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270

# OpenAI
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_VECTOR_STORE_ID = os.environ.get('OPENAI_VECTOR_STORE_ID', '')

# Asterisk / call-centre
ASTERISK_SECRET            = os.environ.get('ASTERISK_SECRET', '')
COMPANY_NAME               = os.environ.get('COMPANY_NAME', 'Future Smart Support')
HUMAN_TRANSFER_EXTENSION   = os.environ.get('HUMAN_TRANSFER_EXTENSION', '200')
MAX_CONVERSATION_TURNS     = int(os.environ.get('MAX_CONVERSATION_TURNS', '10'))
TURN_RECORD_TIMEOUT        = int(os.environ.get('TURN_RECORD_TIMEOUT', '30'))
TURN_SILENCE_TIMEOUT       = int(os.environ.get('TURN_SILENCE_TIMEOUT', '5'))
DJANGO_API_BASE_URL        = os.environ.get('DJANGO_API_BASE_URL', 'http://127.0.0.1:8000')
ASTERISK_SOUNDS_DIR        = os.environ.get('ASTERISK_SOUNDS_DIR', '/var/lib/asterisk/sounds/custom')
WELCOME_SOUND_NAME         = os.environ.get('WELCOME_SOUND_NAME', 'welcome_future_smart')
CALL_RESPONSES_ROOT        = os.environ.get(
    'CALL_RESPONSES_ROOT',
    str(BASE_DIR / 'media' / 'call_responses'),
)

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS — Vite dev server; in production restrict to portal origin
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
CORS_ALLOW_CREDENTIALS = True

# Email
EMAIL_BACKEND      = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST         = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT         = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER    = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS      = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'alerts@futuresmartsupport.com')

# Portal
PORTAL_BASE_URL             = os.environ.get('PORTAL_BASE_URL', 'http://localhost:5173')
ALERT_CONFIDENCE_THRESHOLD  = float(os.environ.get('ALERT_CONFIDENCE_THRESHOLD', '0.6'))
PORTAL_NOTIFICATION_EMAILS  = [
    e.strip() for e in os.environ.get('PORTAL_NOTIFICATION_EMAILS', '').split(',') if e.strip()
]

# Logging
LOG_FILE = os.environ.get('LOG_FILE', str(BASE_DIR / 'logs' / 'app.log'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'apps': {'handlers': ['console', 'file'], 'level': 'DEBUG', 'propagate': False},
        'services': {'handlers': ['console', 'file'], 'level': 'DEBUG', 'propagate': False},
        'tasks': {'handlers': ['console', 'file'], 'level': 'DEBUG', 'propagate': False},
        'watchdog_runner': {'handlers': ['console', 'file'], 'level': 'DEBUG', 'propagate': False},
    },
}
