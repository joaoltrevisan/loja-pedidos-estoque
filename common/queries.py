import re

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from common.serializers import StrictInputMixin, TextField


class QueryIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        # O paginador recebe a query original. Rejeitar decimais aparentando
        # inteiros impede divergencia entre validacao e interpretacao posterior.
        if not isinstance(data, str) or not re.fullmatch(r"[0-9]+", data):
            raise serializers.ValidationError("Use somente digitos inteiros ASCII.")
        return super().to_internal_value(data)


class PageQuerySerializer(StrictInputMixin, serializers.Serializer):
    page = QueryIntegerField(min_value=1, max_value=1000000, required=False)
    page_size = QueryIntegerField(min_value=1, max_value=100, required=False)
    ordering = TextField(max_length=100, required=False, default="id")


@extend_schema_field({"type": "string", "enum": ["true", "false"]})
class QueryBooleanField(serializers.Field):
    def to_internal_value(self, data):
        if data not in ("true", "false"):
            raise serializers.ValidationError("Use true ou false.")
        return data == "true"
