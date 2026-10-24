from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from rest_framework import serializers

from common.limits import BRAZILIAN_STATES, MAX_ITEM_QUANTITY, MAX_ORDER_ITEMS
from common.queries import PageQuerySerializer, QueryIntegerField
from common.serializers import JSONIntegerField, StrictInputMixin, TextField
from common.validation import MAX_ID

from .models import Order, OrderItem, Shipment, SimulatedPayment
from .services import create_order
from .validation import ADDRESS_FIELDS, validate_order_input


class OrderItemInputSerializer(StrictInputMixin, serializers.Serializer):
    product_id = JSONIntegerField(min_value=1, max_value=MAX_ID)
    quantity = JSONIntegerField(min_value=1, max_value=MAX_ITEM_QUANTITY)


class ShippingAddressInputSerializer(StrictInputMixin, serializers.Serializer):
    recipient = TextField(max_length=150)
    street = TextField(max_length=200)
    number = TextField(max_length=20)
    complement = TextField(max_length=100, required=False, allow_blank=True)
    district = TextField(max_length=100)
    city = TextField(max_length=100)
    state = serializers.ChoiceField(choices=BRAZILIAN_STATES)
    postal_code = TextField(max_length=8, validators=[RegexValidator(r"^[0-9]{8}$")])


class OrderCreateSerializer(StrictInputMixin, serializers.Serializer):
    items = OrderItemInputSerializer(many=True, allow_empty=False, max_length=MAX_ORDER_ITEMS)
    shipping_address = ShippingAddressInputSerializer()

    def validate(self, attrs):
        try:
            items, address = validate_order_input(**attrs)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return {"items": items, "shipping_address": address}

    def create(self, validated_data):
        try:
            return create_order(user=self.context["request"].user, **validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ("product_id", "product_sku", "product_name", "quantity", "unit_price", "subtotal")
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    payment_mode = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "customer_id",
            "status",
            "currency",
            "total",
            "shipping_address",
            "items",
            "created_at",
            "updated_at",
            "paid_at",
            "cancelled_at",
            "shipped_at",
            "delivered_at",
            "payment_mode",
        )
        read_only_fields = fields

    def get_shipping_address(self, order):
        return {key: getattr(order, f"shipping_{key}") for key in (*ADDRESS_FIELDS, "country")}

    def get_items(self, order):
        items = getattr(order, "ordered_items", None)
        if items is None:
            items = order.items.order_by("product_id")
        return OrderItemSerializer(items, many=True).data

    def get_payment_mode(self, order):
        return "SIMULATED_NO_REAL_CHARGE"


class EmptyActionSerializer(StrictInputMixin, serializers.Serializer):
    pass


class ShippingActionSerializer(StrictInputMixin, serializers.Serializer):
    tracking_code = TextField(max_length=100, allow_blank=True, required=False, default="")


class SimulatedPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulatedPayment
        fields = ("id", "amount", "reference", "approved_at", "is_simulated")
        read_only_fields = fields


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ("id", "tracking_code", "shipped_at", "delivered_at")
        read_only_fields = fields


class OrderTransitionSerializer(serializers.Serializer):
    order = OrderSerializer(read_only=True)
    simulated_payment = SimulatedPaymentSerializer(read_only=True, allow_null=True)
    shipment = ShipmentSerializer(read_only=True, allow_null=True)


class OrderQuerySerializer(PageQuerySerializer):
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False)
    customer_id = QueryIntegerField(min_value=1, max_value=MAX_ID, required=False)
    created_from = serializers.DateTimeField(required=False, default_timezone=None)
    created_before = serializers.DateTimeField(required=False, default_timezone=None)

    def validate(self, attrs):
        if (
            "created_from" in attrs
            and "created_before" in attrs
            and attrs["created_from"] >= attrs["created_before"]
        ):
            raise serializers.ValidationError(
                {"created_before": ["O fim deve ser posterior ao inicio."]}
            )
        return attrs


class OrderDetailSerializer(OrderSerializer):
    simulated_payment = SimulatedPaymentSerializer(read_only=True, allow_null=True)
    shipment = ShipmentSerializer(read_only=True, allow_null=True)

    class Meta(OrderSerializer.Meta):
        fields = (*OrderSerializer.Meta.fields, "simulated_payment", "shipment")
        read_only_fields = fields
