import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = bool(os.getenv('VERCEL'))

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-this-key-for-production')

DEBUG = os.getenv('DJANGO_DEBUG', 'False' if IS_VERCEL else 'True').lower() == 'true'

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '.vercel.app',
    'smart-e-learning-ai-platform.vercel.app',
]
extra_allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', '')
if extra_allowed_hosts:
    ALLOWED_HOSTS.extend(host.strip() for host in extra_allowed_hosts.split(',') if host.strip())

CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://smart-e-learning-ai-platform.vercel.app',
]
extra_csrf_origins = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '')
if extra_csrf_origins:
    CSRF_TRUSTED_ORIGINS.extend(origin.strip() for origin in extra_csrf_origins.split(',') if origin.strip())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.accounts',
    'apps.core',
    'apps.courses',
    'apps.learning',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smart_lms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'smart_lms.context_processors.global_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'smart_lms.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path('/tmp/db.sqlite3') if IS_VERCEL else BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
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

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:post_login_redirect'
LOGOUT_REDIRECT_URL = 'core:home'

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

GOOGLE_CLOUD_VISION_API_KEY = os.getenv('GOOGLE_CLOUD_VISION_API_KEY', '')
HF_TOKEN = os.getenv('HF_TOKEN', '')
HUGGINGFACE_HUB_TOKEN = os.getenv('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', HF_TOKEN)
HUGGINGFACE_EMOTION_MODEL = os.getenv('HUGGINGFACE_EMOTION_MODEL', 'dima806/facial_emotions_image_detection')

CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
