from decimal import Decimal

from rest_framework import serializers

from common.queries import PageQuerySerializer, QueryBooleanField
from common.serializers import JSONBooleanField, MoneyInputField, StrictInputMixin, TextField

from .models import Product


class ProductInputSerializer(StrictInputMixin, serializers.Serializer):
    sku = TextField(max_length=64)
    name = TextField(max_length=200)
    description = TextField(max_length=5000, allow_blank=True, required=False)
    price = MoneyInputField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    is_active = JSONBooleanField(required=False)


class ProductSerializer(serializers.ModelSerializer):
    available_quantity = serializers.IntegerField(source="stock.available_quantity", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "description",
            "price",
            "is_active",
            "available_quantity",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProductQuerySerializer(PageQuerySerializer):
    search = TextField(max_length=200, required=False)
    sku = TextField(max_length=64, required=False)
    is_active = QueryBooleanField(required=False)
