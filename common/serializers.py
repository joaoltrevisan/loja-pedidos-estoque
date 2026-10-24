import re
from collections.abc import Mapping

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class StrictInputMixin:
    """Campos desconhecidos ou somente de leitura nunca sao ignorados."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            writable = {key for key, field in self.fields.items() if not field.read_only}
            forbidden = data.keys() - writable
            if forbidden:
                raise serializers.ValidationError(
                    dict.fromkeys(sorted(forbidden), ["Campo nao permitido."])
                )
        return super().to_internal_value(data)


class TextField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        if "\x00" in data:
            raise serializers.ValidationError("Caractere nulo nao permitido.")
        try:
            data.encode("utf-8")
        except UnicodeEncodeError as error:
            raise serializers.ValidationError("Texto Unicode invalido.") from error
        return super().to_internal_value(data)


class JSONIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise serializers.ValidationError("Informe um inteiro JSON.")
        return super().to_internal_value(data)


@extend_schema_field(
    {"type": "string", "pattern": r"^[0-9]{1,8}(\.[0-9]{1,2})?$", "example": "25.90"}
)
class MoneyInputField(serializers.DecimalField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError(
                "Informe dinheiro como texto decimal, por exemplo 25.90."
            )
        if not re.fullmatch(r"[0-9]{1,8}(\.[0-9]{1,2})?", data):
            raise serializers.ValidationError(
                "Use ate oito digitos inteiros e duas casas decimais."
            )
        return super().to_internal_value(data)


class JSONBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            raise serializers.ValidationError("Informe true ou false JSON.")
        return super().to_internal_value(data)
