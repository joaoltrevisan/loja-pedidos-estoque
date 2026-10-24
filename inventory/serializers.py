from rest_framework import serializers

from common.limits import MAX_STOCK_QUANTITY
from common.queries import PageQuerySerializer, QueryIntegerField
from common.serializers import JSONIntegerField, StrictInputMixin, TextField
from common.validation import MAX_ID

from .models import Stock, StockMovement


class StockSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = Stock
        fields = ("product_id", "sku", "available_quantity", "updated_at")
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = (
            "id",
            "product_id",
            "order_id",
            "performed_by_id",
            "movement_type",
            "quantity_delta",
            "created_at",
            "reason",
        )
        read_only_fields = fields


class StockChangeSerializer(StrictInputMixin, serializers.Serializer):
    movement_type = serializers.ChoiceField(choices=("ENTRY", "ADJUSTMENT"))
    quantity_delta = JSONIntegerField(min_value=-MAX_STOCK_QUANTITY, max_value=MAX_STOCK_QUANTITY)
    reason = TextField(max_length=500)


class StockChangeResultSerializer(serializers.Serializer):
    stock = StockSerializer()
    movement = StockMovementSerializer()


class StockQuerySerializer(PageQuerySerializer):
    product_id = QueryIntegerField(min_value=1, max_value=MAX_ID, required=False)
    max_quantity = QueryIntegerField(min_value=0, max_value=MAX_STOCK_QUANTITY, required=False)


class MovementQuerySerializer(PageQuerySerializer):
    product_id = QueryIntegerField(min_value=1, max_value=MAX_ID, required=False)
    order_id = QueryIntegerField(min_value=1, max_value=MAX_ID, required=False)
    movement_type = serializers.ChoiceField(choices=StockMovement.Type.choices, required=False)
