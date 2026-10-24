from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404

from accounts.models import User

MAX_ID = 9223372036854775807


def require_admin(user):
    if (
        not user
        or not user.is_authenticated
        or not User.objects.filter(pk=user.pk, is_active=True, is_staff=True).exists()
    ):
        raise PermissionDenied("Somente administradores podem executar esta operacao.")


def validate_id(value):
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise Http404("Registro nao encontrado.")
    return value


def clean_text(value, field, *, max_length, blank=False):
    if not isinstance(value, str):
        raise ValidationError({field: ["Informe um texto."]})
    value = value.strip()
    if (not blank and not value) or len(value) > max_length or "\x00" in value:
        raise ValidationError({field: [f"Texto invalido; limite de {max_length} caracteres."]})
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValidationError({field: ["Texto Unicode invalido."]}) from error
    return value
