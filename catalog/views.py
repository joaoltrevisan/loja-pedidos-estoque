from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import CanReadOrder, IsStoreAdmin, is_store_admin
from common.api import StorePagination, ordered, query_params, service_validation
from common.validation import validate_id
from common.views import PrivateResponseMixin
from orders.exceptions import OrderConflict

from .models import Product
from .serializers import ProductInputSerializer, ProductQuerySerializer, ProductSerializer
from .services import save_product


class ProductListView(PrivateResponseMixin, generics.ListAPIView):
    serializer_class = ProductSerializer
    pagination_class = StorePagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsStoreAdmin()]
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [CanReadOrder()]
        return [IsAuthenticated()]

    def get_queryset(self):
        params = query_params(self.request, ProductQuerySerializer)
        queryset = Product.objects.select_related("stock")
        admin = is_store_admin(self.request.user)
        if not admin:
            queryset = queryset.filter(is_active=True)
        if "is_active" in params:
            if not admin:
                raise PermissionDenied("Filtro is_active exclusivo de administradores.")
            queryset = queryset.filter(is_active=params["is_active"])
        if "sku" in params:
            queryset = queryset.filter(sku=params["sku"])
        if "search" in params:
            queryset = queryset.filter(
                Q(name__icontains=params["search"]) | Q(sku__icontains=params["search"])
            )
        return ordered(
            queryset,
            params["ordering"],
            {key: key for key in ("id", "sku", "name", "price", "created_at")},
        )

    def post(self, request):
        return product_write(request)


class ProductDetailView(PrivateResponseMixin, generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_url_kwarg = "product_id"

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsStoreAdmin()]
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [CanReadOrder()]
        return [IsAuthenticated()]

    def get_object(self):
        product_id = validate_id(self.kwargs["product_id"])
        queryset = Product.objects.select_related("stock")
        if not is_store_admin(self.request.user):
            queryset = queryset.filter(is_active=True)
        return get_object_or_404(queryset, pk=product_id)

    def patch(self, request, product_id):
        return product_write(request, product_id)


def product_write(request, product_id=None):
    serializer = ProductInputSerializer(data=request.data, partial=product_id is not None)
    serializer.is_valid(raise_exception=True)
    try:
        product = save_product(
            user=request.user, data=serializer.validated_data, product_id=product_id
        )
    except DjangoValidationError as error:
        raise service_validation(error) from error
    except OrderConflict as error:
        return Response({"code": error.code, "detail": error.message}, status=409)
    return Response(
        ProductSerializer(product).data,
        status=status.HTTP_201_CREATED if product_id is None else 200,
    )
