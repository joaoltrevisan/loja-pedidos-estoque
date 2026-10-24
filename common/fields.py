import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class StrictIntegerField(models.IntegerField):
    """Evita a conversao silenciosa de fracionarios e booleanos pelo ORM."""

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValidationError("Informe uma quantidade inteira, sem booleanos.")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
            return int(value)
        if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
            return int(value)
        raise ValidationError("Informe uma quantidade inteira, sem fracionarios.")

    def get_prep_value(self, value):
        return self.to_python(value)
