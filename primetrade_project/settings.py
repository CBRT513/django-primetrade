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
SSO_SCOPES = config('SSO_SCOPES', default='openid email profile roles')

# Temporary admin bypass for authorization during rollout (comma-separated emails)
ADMIN_BYPASS_EMAILS = [e.strip() for e in config('ADMIN_BYPASS_EMAILS', default='').split(',') if e.strip()]

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
LOGIN_URL = '/auth/login/'  # Direct to SSO login to prevent redirect loop
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

# Build CSRF_TRUSTED_ORIGINS dynamically from ALLOWED_HOSTS and SSO_BASE_URL
from urllib.parse import urlsplit

trusted_origins = set()
for host in ALLOWED_HOSTS:
    host = host.strip()
    if host:
        trusted_origins.add(f"https://{host}")
        if DEBUG:
            trusted_origins.add(f"http://{host}")
# Include SSO base origin
try:
    sso_parts = urlsplit(SSO_BASE_URL)
    if sso_parts.scheme and sso_parts.netloc:
        trusted_origins.add(f"{sso_parts.scheme}://{sso_parts.netloc}")
except Exception:
    pass
CSRF_TRUSTED_ORIGINS = sorted(trusted_origins)

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
# Storage configuration - Use S3 in production, local filesystem in development
USE_S3 = config('USE_S3', default='False', cast=bool)

if USE_S3:
    # AWS S3 Configuration for production
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='primetrade-documents')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-2')  # Ohio region
    # Don't set AWS_S3_CUSTOM_DOMAIN - it prevents signed URL generation
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',  # 24 hours
    }
    AWS_DEFAULT_ACL = None  # Use bucket ACL
    AWS_S3_FILE_OVERWRITE = False  # Never overwrite existing files
    AWS_QUERYSTRING_AUTH = True  # Use signed URLs
    AWS_QUERYSTRING_EXPIRE = 86400  # Signed URLs expire after 24 hours

    # Use S3 for media files (PDFs)
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

    # MEDIA_URL not needed - S3 storage backend generates signed URLs automatically
else:
    # Local development - use filesystem storage
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

    # Media files (PDFs) - local storage
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

# Production CSRF Origins are built dynamically above from ALLOWED_HOSTS and SSO_BASE_URL
