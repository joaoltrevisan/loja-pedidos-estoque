from django.contrib.staticfiles.views import serve
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import health

handler404 = "config.views.not_found"

urlpatterns = [
    path("health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/products/", include("catalog.urls")),
    path("api/stock/", include("inventory.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# Servidor local de demonstracao; nao configura hosting de producao.
urlpatterns += [
    re_path(
        r"^static/(?P<path>drf_spectacular_sidecar/swagger-ui-dist/"
        r"(?:swagger-ui-bundle\.js|swagger-ui-standalone-preset\.js|swagger-ui\.css|favicon-32x32\.png))$",
        serve,
        {"insecure": True},
    )
]

from common.schema import configure_schema  # noqa: E402

configure_schema()
