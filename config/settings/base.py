import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "django.contrib.staticfiles",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "accounts",
    "catalog",
    "inventory",
    "orders",
    "reports",
]
MIDDLEWARE = []
ROOT_URLCONF = "config.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "loja"),
        "USER": os.environ.get("PGUSER", "loja"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 5},
    }
}
USE_TZ = True
TIME_ZONE = "America/Sao_Paulo"
LANGUAGE_CODE = "pt-br"
ENABLE_DEMO_DATA = os.environ.get("ENABLE_DEMO_DATA", "false").lower() == "true"

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "common.api.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Nao existe proxy neste ambiente; ignore X-Forwarded-For enviado pelo cliente.
    "NUM_PROXIES": 0,
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.DatabaseJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "register": "5/min",
        "login": "20/min",
        "refresh": "60/min",
        "profile": "120/min",
    },
}
STATIC_URL = "/static/"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
SPECTACULAR_SETTINGS = {
    "TITLE": "Loja ficticia — pedidos e estoque",
    "DESCRIPTION": (
        "API de portfolio. Dados ficticios; pagamentos SIMULADOS, SEM COBRANCA REAL. "
        "Relatorios exclusivos do administrador. "
        "Use login, copie access e clique Authorize (Bearer)."
    ),
    "VERSION": "0.8.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SERVE_AUTHENTICATION": [],
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": False,
        "validatorUrl": None,
        "supportedSubmitMethods": ["get", "post", "patch"],
    },
    "COMPONENT_SPLIT_REQUEST": True,
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "ALGORITHM": "HS256",
    "AUDIENCE": "loja-api",
    "ISSUER": "loja-portfolio-local",
    "CHECK_USER_IS_ACTIVE": True,
    "CHECK_REVOKE_TOKEN": True,
    "TOKEN_REFRESH_SERIALIZER": "accounts.serializers.ActiveUserRefreshSerializer",
}
