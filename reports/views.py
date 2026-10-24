from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStoreAdmin
from common.api import StorePagination, ordered, query_params, service_validation
from common.views import PrivateResponseMixin

from . import selectors, serializers


class ReportSummaryView(PrivateResponseMixin, APIView):
    permission_classes = (IsStoreAdmin,)

    def get(self, request):
        params = query_params(request, self.query_serializer_class)
        try:
            result = self.report(user=request.user, **params)
        except DjangoValidationError as error:
            raise service_validation(error) from error
        return Response(self.output_serializer_class(result).data)


class RevenueView(ReportSummaryView):
    query_serializer_class = serializers.RevenueQuerySerializer
    output_serializer_class = serializers.RevenueReportSerializer
    report = staticmethod(selectors.revenue_report)


class AverageTicketView(ReportSummaryView):
    query_serializer_class = serializers.PeriodQuerySerializer
    output_serializer_class = serializers.AverageTicketSerializer
    report = staticmethod(selectors.average_ticket_report)


class OrderStatusView(ReportSummaryView):
    query_serializer_class = serializers.PeriodQuerySerializer
    output_serializer_class = serializers.OrderStatusReportSerializer
    report = staticmethod(selectors.orders_by_status_report)


class ReportListView(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = (IsStoreAdmin,)
    pagination_class = StorePagination
    tie_breaker = "id"

    def get_queryset(self):
        params = query_params(self.request, self.query_serializer_class)
        kwargs = {
            key: value
            for key, value in params.items()
            if key not in ("page", "page_size", "ordering")
        }
        try:
            queryset = self.report(user=self.request.user, **kwargs)
        except DjangoValidationError as error:
            raise service_validation(error) from error
        return ordered(
            queryset, params["ordering"], self.allowed_ordering, tie_breaker=self.tie_breaker
        )


class TopProductsView(ReportListView):
    query_serializer_class = serializers.ProductRankingQuerySerializer
    serializer_class = serializers.ProductRankingSerializer
    report = staticmethod(selectors.top_products)
    allowed_ordering = {key: key for key in ("product_id", "units_sold", "simulated_revenue")}
    tie_breaker = "product_id"


class TopCustomersView(ReportListView):
    query_serializer_class = serializers.CustomerRankingQuerySerializer
    serializer_class = serializers.CustomerRankingSerializer
    report = staticmethod(selectors.top_customers)
    allowed_ordering = {key: key for key in ("customer_id", "paid_orders", "simulated_revenue")}
    tie_breaker = "customer_id"


class LowStockView(ReportListView):
    query_serializer_class = serializers.LowStockQuerySerializer
    serializer_class = serializers.LowStockSerializer
    report = staticmethod(selectors.low_stock)
    allowed_ordering = {key: key for key in ("product_id", "available_quantity")}
    tie_breaker = "product_id"


class OldestPendingView(ReportListView):
    query_serializer_class = serializers.PendingQuerySerializer
    serializer_class = serializers.PendingOrderSerializer
    report = staticmethod(selectors.oldest_pending)
    allowed_ordering = {key: key for key in ("id", "created_at", "total")}
