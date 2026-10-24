import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY no ambiente de desenvolvimento.")
