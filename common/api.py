from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        original = response.data
        response.data = {
            "code": "validation_error"
            if isinstance(exc, ValidationError)
            else getattr(
                exc,
                "default_code",
                "not_found" if response.status_code == 404 else "permission_denied",
            ),
            "detail": (
                "Revise os campos informados."
                if isinstance(exc, ValidationError)
                else original.get("detail", "Requisicao rejeitada.")
            ),
            "errors": original if isinstance(exc, ValidationError) else None,
        }
    return response


def service_validation(error):
    assert isinstance(error, DjangoValidationError)
    return ValidationError(
        error.message_dict
        if hasattr(error, "message_dict")
        else {"non_field_errors": error.messages}
    )


class StorePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def query_params(request, serializer_class):
    repeated = [key for key in request.query_params if len(request.query_params.getlist(key)) != 1]
    if repeated:
        raise ValidationError(dict.fromkeys(repeated, ["Parametro repetido nao permitido."]))
    # Um dict evita o tratamento de formulario HTML do DRF, que troca valores
    # vazios por defaults. Parametro presente e vazio precisa ser validado.
    serializer = serializer_class(
        data={key: request.query_params[key] for key in request.query_params}
    )
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def ordered(queryset, value, allowed, *, tie_breaker="id"):
    fields = value.split(",")
    if (
        len(fields) > 3
        or len(set(fields)) != len(fields)
        or any(field.removeprefix("-") not in allowed for field in fields)
    ):
        raise ValidationError({"ordering": [f"Use ate tres campos de: {', '.join(allowed)}."]})
    # Desempate estavel para paginacao; nunca repassa nomes arbitrarios ao ORM.
    ordering = [
        ("-" if field.startswith("-") else "") + allowed[field.lstrip("-")] for field in fields
    ]
    if not any(field.lstrip("-") == tie_breaker for field in ordering):
        ordering.append(tie_breaker)
    return queryset.order_by(*ordering)
