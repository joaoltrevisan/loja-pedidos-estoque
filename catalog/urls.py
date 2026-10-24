from django.urls import path

from .views import ProductDetailView, ProductListView

app_name = "catalog"
urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("<int:product_id>/", ProductDetailView.as_view(), name="detail"),
]
