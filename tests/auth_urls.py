"""Rotas EXCLUSIVAS dos testes; nao sao incluidas na URLconf da aplicacao."""

from django.shortcuts import get_object_or_404
from django.urls import include, path
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanReadOrder, IsCustomer, IsStoreAdmin
from orders.selectors import orders_visible_to


class CustomerProbe(APIView):
    permission_classes = (IsCustomer,)

    def post(self, request):
        return Response({"ok": True})


class AdminProbe(CustomerProbe):
    permission_classes = (IsStoreAdmin,)


class OrderProbe(APIView):
    permission_classes = (CanReadOrder,)

    def get(self, request, pk=None):
        queryset = orders_visible_to(request.user)
        if pk is None:
            return Response(list(queryset.order_by("id").values_list("id", flat=True)))
        order = get_object_or_404(queryset, pk=pk)
        self.check_object_permissions(request, order)
        return Response({"id": order.pk})

    def post(self, request, pk=None):
        # Deve ser barrado pela permissao, antes de alcancar este metodo.
        raise AssertionError("Permissao de leitura permitiu escrita.")


urlpatterns = [
    path("", include("config.urls")),
    path("_test/customer/", CustomerProbe.as_view()),
    path("_test/admin/", AdminProbe.as_view()),
    path("_test/orders/", OrderProbe.as_view()),
    path("_test/orders/<int:pk>/", OrderProbe.as_view()),
]
