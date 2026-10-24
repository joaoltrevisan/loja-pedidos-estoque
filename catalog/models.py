from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from common.limits import MAX_UNIT_PRICE, SKU_PATTERN
from common.models import TimestampedModel


class Product(TimestampedModel):
    sku = models.CharField(max_length=64, unique=True, validators=[RegexValidator(SKU_PATTERN)])
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0, price__lte=MAX_UNIT_PRICE),
                name="product_price_positive_finite",
            ),
            models.CheckConstraint(
                condition=models.Q(sku__regex=SKU_PATTERN), name="product_sku_format"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"), name="product_name_required"
            ),
        ]

    def __str__(self):
        return self.sku
