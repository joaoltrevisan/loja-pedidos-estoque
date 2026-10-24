from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStoreAdmin
from common.api import StorePagination, ordered, query_params, service_validation
from common.validation import validate_id
from common.views import PrivateResponseMixin
from orders.exceptions import OrderConflict

from .models import Stock, StockMovement
from .serializers import (
    MovementQuerySerializer,
    StockChangeSerializer,
    StockMovementSerializer,
    StockQuerySerializer,
    StockSerializer,
)
from .services import change_stock


class StockListView(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = (IsStoreAdmin,)
    serializer_class = StockSerializer
    pagination_class = StorePagination

    def get_queryset(self):
        params = query_params(self.request, StockQuerySerializer)
        qs = Stock.objects.select_related("product")
        if "product_id" in params:
            qs = qs.filter(product_id=params["product_id"])
        if "max_quantity" in params:
            qs = qs.filter(available_quantity__lte=params["max_quantity"])
        return ordered(
            qs,
            params["ordering"],
            {
                "id": "id",
                "product_id": "product_id",
                "available_quantity": "available_quantity",
                "updated_at": "updated_at",
            },
        )


class StockDetailView(PrivateResponseMixin, generics.RetrieveAPIView):
    permission_classes = (IsStoreAdmin,)
    serializer_class = StockSerializer

    def get_object(self):
        return get_object_or_404(
            Stock.objects.select_related("product"),
            product_id=validate_id(self.kwargs["product_id"]),
        )


class StockChangeView(PrivateResponseMixin, APIView):
    permission_classes = (IsStoreAdmin,)

    def post(self, request, product_id):
        serializer = StockChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            stock, movement = change_stock(
                user=request.user, product_id=product_id, **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise service_validation(error) from error
        except OrderConflict as error:
            return Response({"code": error.code, "detail": error.message}, status=409)
        return Response(
            {
                "stock": StockSerializer(stock).data,
                "movement": StockMovementSerializer(movement).data,
            },
            status=201,
        )


class StockMovementListView(PrivateResponseMixin, generics.ListAPIView):
    permission_classes = (IsStoreAdmin,)
    serializer_class = StockMovementSerializer
    pagination_class = StorePagination

    def get_queryset(self):
        params = query_params(self.request, MovementQuerySerializer)
        qs = StockMovement.objects.all()
        for key in ("product_id", "order_id", "movement_type"):
            if key in params:
                qs = qs.filter(**{key: params[key]})
        return ordered(
            qs, params["ordering"], {key: key for key in ("id", "created_at", "product_id")}
        )
