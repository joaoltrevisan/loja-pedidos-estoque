from django.urls import path

from .views import (
    OrderCancelView,
    OrderCreateView,
    OrderDeliverView,
    OrderDetailView,
    OrderShipView,
    SimulatedPaymentView,
)

app_name = "orders"
urlpatterns = [
    path("", OrderCreateView.as_view(), name="create"),
    path("<int:order_id>/", OrderDetailView.as_view(), name="detail"),
    path(
        "<int:order_id>/simulated-payment/",
        SimulatedPaymentView.as_view(),
        name="simulated-payment",
    ),
    path("<int:order_id>/cancel/", OrderCancelView.as_view(), name="cancel"),
    path("<int:order_id>/ship/", OrderShipView.as_view(), name="ship"),
    path("<int:order_id>/deliver/", OrderDeliverView.as_view(), name="deliver"),
]
