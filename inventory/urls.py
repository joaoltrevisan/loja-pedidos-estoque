from django.urls import path

from .views import StockChangeView, StockDetailView, StockListView, StockMovementListView

app_name = "inventory"
urlpatterns = [
    path("", StockListView.as_view(), name="list"),
    path("movements/", StockMovementListView.as_view(), name="movements"),
    path("<int:product_id>/", StockDetailView.as_view(), name="detail"),
    path("<int:product_id>/movements/", StockChangeView.as_view(), name="change"),
]
