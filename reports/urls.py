from django.urls import path

from .views import (
    AverageTicketView,
    LowStockView,
    OldestPendingView,
    OrderStatusView,
    RevenueView,
    TopCustomersView,
    TopProductsView,
)

app_name = "reports"
urlpatterns = [
    path("revenue/", RevenueView.as_view(), name="revenue"),
    path("average-ticket/", AverageTicketView.as_view(), name="average-ticket"),
    path("top-products/", TopProductsView.as_view(), name="top-products"),
    path("top-customers/", TopCustomersView.as_view(), name="top-customers"),
    path("low-stock/", LowStockView.as_view(), name="low-stock"),
    path("orders-by-status/", OrderStatusView.as_view(), name="orders-by-status"),
    path("oldest-pending/", OldestPendingView.as_view(), name="oldest-pending"),
]
