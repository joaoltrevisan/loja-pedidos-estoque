from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanReadOrder, IsCustomer, IsStoreAdmin, is_store_admin
from common.api import StorePagination, ordered, query_params
from common.validation import validate_id
from common.views import PrivateResponseMixin

from .exceptions import OrderConflict
from .lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from .models import OrderItem
from .selectors import orders_visible_to
from .serializers import (
    EmptyActionSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderQuerySerializer,
    OrderSerializer,
    OrderTransitionSerializer,
    ShippingActionSerializer,
)


class OrderCreateView(PrivateResponseMixin, generics.ListAPIView):
    serializer_class = OrderDetailSerializer
    pagination_class = StorePagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomer()]
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [CanReadOrder()]
        return [IsAuthenticated()]

    def get_queryset(self):
        params = query_params(self.request, OrderQuerySerializer)
        qs = readable_orders(self.request.user)
        if "customer_id" in params:
            if not is_store_admin(self.request.user):
                raise PermissionDenied("Filtro customer_id exclusivo de administradores.")
            qs = qs.filter(customer_id=params["customer_id"])
        if "status" in params:
            qs = qs.filter(status=params["status"])
        if "created_from" in params:
            qs = qs.filter(created_at__gte=params["created_from"])
        if "created_before" in params:
            qs = qs.filter(created_at__lt=params["created_before"])
        return ordered(
            qs, params["ordering"], {key: key for key in ("id", "created_at", "total", "status")}
        )

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            order = serializer.save()
        except OrderConflict as error:
            return Response(
                {"code": error.code, "detail": error.message}, status=status.HTTP_409_CONFLICT
            )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


def readable_orders(user):
    return (
        orders_visible_to(user)
        .select_related("simulated_payment", "shipment")
        .prefetch_related(
            Prefetch(
                "items", queryset=OrderItem.objects.order_by("product_id"), to_attr="ordered_items"
            )
        )
    )


class OrderDetailView(PrivateResponseMixin, generics.RetrieveAPIView):
    permission_classes = (CanReadOrder,)
    serializer_class = OrderDetailSerializer

    def get_object(self):
        order = get_object_or_404(
            readable_orders(self.request.user), pk=validate_id(self.kwargs["order_id"])
        )
        self.check_object_permissions(self.request, order)
        return order


class OrderActionView(PrivateResponseMixin, APIView):
    permission_classes = (IsStoreAdmin,)
    input_serializer_class = EmptyActionSerializer

    def post(self, request, order_id):
        serializer = self.input_serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = self.action(user=request.user, order_id=order_id, **serializer.validated_data)
        except OrderConflict as error:
            return Response(
                {"code": error.code, "detail": error.message}, status=status.HTTP_409_CONFLICT
            )
        except DjangoValidationError as error:
            raise ValidationError(error.message_dict) from error
        return Response(OrderTransitionSerializer(result).data)


class SimulatedPaymentView(OrderActionView):
    action = staticmethod(approve_simulated_payment)


class OrderCancelView(OrderActionView):
    permission_classes = (IsCustomer,)
    action = staticmethod(cancel_order)


class OrderShipView(OrderActionView):
    input_serializer_class = ShippingActionSerializer
    action = staticmethod(ship_order)


class OrderDeliverView(OrderActionView):
    action = staticmethod(deliver_order)
