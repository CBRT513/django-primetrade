import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = config('SECRET_KEY')  # No default - must be set in .env
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# SSO Configuration
SSO_BASE_URL = config('SSO_BASE_URL', default='https://sso.barge2rail.com')
SSO_CLIENT_ID = config('SSO_CLIENT_ID', default=None)
SSO_CLIENT_SECRET = config('SSO_CLIENT_SECRET', default=None)
SSO_REDIRECT_URI = config('SSO_REDIRECT_URI', default='http://localhost:8001/auth/callback/')
SSO_SCOPES = config('SSO_SCOPES', default='openid email profile')

# Validate SSO credentials are configured
if not SSO_CLIENT_ID or not SSO_CLIENT_SECRET:
    import warnings
    warnings.warn(
        "SSO credentials not configured! "
        "Copy .env.example to .env and add your credentials from SSO admin panel.",
        UserWarning
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'bol_system',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add WhiteNoise right after SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'primetrade_project.urls'

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

WSGI_APPLICATION = 'primetrade_project.wsgi.application'

# Database - SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Cache configuration for OAuth state storage
# Using database cache for portability (no Redis dependency)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'primetrade_cache_table',
        'TIMEOUT': 600,  # 10 minutes default
        'OPTIONS': {
            'MAX_ENTRIES': 10000
        }
    }
}

# REST Framework - Require authentication
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# Authentication URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# CSRF and Session Security
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # Must be False for JavaScript to read CSRF token
SESSION_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']

# Session Configuration for OAuth Compatibility
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Use database sessions
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow cookies across OAuth redirects
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = False  # Only save when modified
SESSION_COOKIE_NAME = 'primetrade_sessionid'  # Unique session cookie name

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise configuration for serving static files with DEBUG=False
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (PDFs)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'primetrade.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'bol_system': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'primetrade_project.auth_views': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'oauth.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
        },
    },
}
# Production Database Configuration
import dj_database_url
if config('DATABASE_URL', default=None):
    DATABASES['default'] = dj_database_url.parse(
        config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )

# Production CSRF Origins
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        'https://prt.barge2rail.com',
        'https://primetrade-u2a6.onrender.com',
        'https://sso.barge2rail.com'
    ]
