import re

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.api import service_validation
from common.limits import MAX_STOCK_QUANTITY
from common.queries import PageQuerySerializer, QueryIntegerField
from common.serializers import StrictInputMixin, TextField

from .periods import ReportPeriod


class CalendarDateField(serializers.DateField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data):
            raise serializers.ValidationError("Use data no formato YYYY-MM-DD.")
        return super().to_internal_value(data)


class PeriodQuerySerializer(StrictInputMixin, serializers.Serializer):
    start = CalendarDateField()
    end = CalendarDateField()

    def validate(self, attrs):
        try:
            ReportPeriod(attrs["start"], attrs["end"])
        except DjangoValidationError as error:
            raise service_validation(error) from error
        return attrs


class RevenueQuerySerializer(PeriodQuerySerializer):
    group_by = serializers.ChoiceField(choices=("day", "month"), default="day", required=False)


class ProductRankingQuerySerializer(PeriodQuerySerializer, PageQuerySerializer):
    ordering = TextField(max_length=100, default="-units_sold", required=False)


class CustomerRankingQuerySerializer(PeriodQuerySerializer, PageQuerySerializer):
    ordering = TextField(max_length=100, default="-simulated_revenue", required=False)


class LowStockQuerySerializer(PageQuerySerializer):
    threshold = QueryIntegerField(min_value=0, max_value=MAX_STOCK_QUANTITY)
    ordering = TextField(max_length=100, default="available_quantity", required=False)


class PendingQuerySerializer(PageQuerySerializer):
    min_age_hours = QueryIntegerField(min_value=0, max_value=87600, default=0, required=False)
    ordering = TextField(max_length=100, default="created_at", required=False)


class PeriodMetadataSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    timezone = serializers.CharField()


class FinancialMetadataSerializer(PeriodMetadataSerializer):
    currency = serializers.CharField()
    payment_mode = serializers.CharField()
    notice = serializers.CharField()


class RevenueBucketSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    amount = serializers.DecimalField(max_digits=40, decimal_places=2)
    paid_orders = serializers.IntegerField()


class RevenueReportSerializer(FinancialMetadataSerializer):
    group_by = serializers.ChoiceField(choices=("day", "month"))
    total = serializers.DecimalField(max_digits=40, decimal_places=2)
    paid_orders = serializers.IntegerField()
    series = RevenueBucketSerializer(many=True)


class AverageTicketSerializer(FinancialMetadataSerializer):
    total = serializers.DecimalField(max_digits=40, decimal_places=2)
    paid_orders = serializers.IntegerField()
    average_ticket = serializers.DecimalField(max_digits=40, decimal_places=2)


class ProductRankingSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    sku = serializers.CharField()
    name = serializers.CharField()
    units_sold = serializers.IntegerField()
    simulated_revenue = serializers.DecimalField(max_digits=40, decimal_places=2)


class CustomerRankingSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    name = serializers.CharField()
    paid_orders = serializers.IntegerField()
    simulated_revenue = serializers.DecimalField(max_digits=40, decimal_places=2)


class LowStockSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    sku = serializers.CharField(source="product.sku")
    name = serializers.CharField(source="product.name")
    available_quantity = serializers.IntegerField()


class PendingOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    customer_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    total = serializers.DecimalField(max_digits=16, decimal_places=2)
    currency = serializers.CharField()


class StatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class OrderStatusReportSerializer(PeriodMetadataSerializer):
    date_basis = serializers.CharField()
    total_orders = serializers.IntegerField()
    statuses = StatusCountSerializer(many=True)
