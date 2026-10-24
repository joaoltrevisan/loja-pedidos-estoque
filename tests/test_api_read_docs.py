from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from orders.lifecycle import approve_simulated_payment, deliver_order, ship_order
from orders.models import Order
from orders.services import create_order
from tests.order_fixtures import ADDRESS, build_order_fixtures, order_domain_snapshot


class ReadAndDocumentationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_order_fixtures(cls)
        cls.own = create_order(
            user=cls.user,
            items=[{"product_id": cls.product.pk, "quantity": 1}],
            shipping_address=ADDRESS,
        )
        cls.foreign = create_order(
            user=cls.other,
            items=[{"product_id": cls.second.pk, "quantity": 2}],
            shipping_address=ADDRESS,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.auth(self.user)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def test_customer_list_and_detail_are_scoped_before_lookup(self):
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.own.pk)
        self.assertEqual(self.client.get(f"/api/orders/{self.own.pk}/").status_code, 200)
        foreign = self.client.get(f"/api/orders/{self.foreign.pk}/")
        missing = self.client.get("/api/orders/999999/")
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.data, missing.data)
        self.assertNotIn("shipping_address", foreign.data)
        self.assertEqual(
            self.client.get(f"/api/orders/?customer_id={self.foreign.customer_id}").status_code, 403
        )

    def test_admin_can_read_all_and_filter_by_customer(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get("/api/orders/").data["count"], 2)
        self.assertEqual(self.client.get(f"/api/orders/{self.foreign.pk}/").status_code, 200)
        response = self.client.get(
            f"/api/orders/?customer_id={self.own.customer_id}&ordering=-total&page_size=1"
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.own.pk)

    def test_current_role_and_active_status_apply_to_real_read_routes(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)
        orphan = User.objects.create_user("reader@example.com", name="Ficticio")
        self.auth(orphan)
        self.assertEqual(self.client.get("/api/orders/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/orders/{self.own.pk}/").status_code, 403)
        self.auth(self.admin)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        self.assertEqual(self.client.get("/api/orders/").status_code, 403)
        self.auth(self.user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get("/api/orders/").status_code, 401)

    def test_detail_contains_simulated_payment_and_shipment_without_real_charge(self):
        pending = self.client.get(f"/api/orders/{self.own.pk}/")
        self.assertIsNone(pending.data["simulated_payment"])
        self.assertIsNone(pending.data["shipment"])
        approve_simulated_payment(user=self.admin, order_id=self.own.pk)
        ship_order(user=self.admin, order_id=self.own.pk, tracking_code="SIMULATED-READ-001")
        deliver_order(user=self.admin, order_id=self.own.pk)
        response = self.client.get(f"/api/orders/{self.own.pk}/")
        self.assertEqual(response.data["status"], "DELIVERED")
        self.assertEqual(response.data["total"], "25.90")
        self.assertTrue(response.data["simulated_payment"]["is_simulated"])
        self.assertEqual(response.data["simulated_payment"]["amount"], "25.90")
        self.assertEqual(
            response.data["paid_at"], response.data["simulated_payment"]["approved_at"]
        )
        self.assertEqual(response.data["delivered_at"], response.data["shipment"]["delivered_at"])
        self.assertEqual(response.data["payment_mode"], "SIMULATED_NO_REAL_CHARGE")
        self.assertIn("no-store", response["Cache-Control"])

    def test_status_date_bounds_and_pagination_ordering(self):
        self.auth(self.admin)
        start = self.own.created_at.replace(microsecond=0)
        end = start + timedelta(days=1)
        Order.objects.filter(pk=self.own.pk).update(created_at=start, updated_at=start)
        Order.objects.filter(pk=self.foreign.pk).update(created_at=end, updated_at=end)
        response = self.client.get(
            "/api/orders/",
            {
                "created_from": start.isoformat(),
                "created_before": end.isoformat(),
                "status": "PENDING_PAYMENT",
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([x["id"] for x in response.data["results"]], [self.own.pk])
        ordered = self.client.get("/api/orders/?ordering=-total&page_size=1")
        self.assertEqual(ordered.data["results"][0]["id"], self.own.pk)
        self.assertIsNotNone(ordered.data["next"])
        self.assertEqual(
            self.client.get(ordered.data["next"]).data["results"][0]["id"], self.foreign.pk
        )
        self.assertEqual(self.client.get("/api/orders/?status=PAID").data["results"], [])

    def test_order_invalid_filters_and_oversized_ids_are_safe(self):
        self.auth(self.admin)
        for query in (
            "status=WRONG",
            "created_from=abc",
            "created_from=2026-02-01&created_before=2026-01-01",
            "customer_id=0",
            "customer_id=9223372036854775808",
            "ordering=customer__user__email",
            "ordering=?",
            "page_size=101",
            "page=1&page=2",
            "foo=1",
        ):
            self.assertEqual(self.client.get("/api/orders/?" + query).status_code, 400, query)
        for order_id in (0, 9223372036854775808, 10**100):
            self.assertEqual(self.client.get(f"/api/orders/{order_id}/").status_code, 404)

    def test_pagination_rejects_decimal_text_consistently_across_all_lists(self):
        self.auth(self.admin)
        for route in ("/api/products/", "/api/stock/", "/api/stock/movements/", "/api/orders/"):
            for field in ("page", "page_size"):
                for value in ("1.0", "1.00", "1e0", " 1", "+1", "１"):
                    with self.subTest(route=route, field=field, value=value):
                        response = self.client.get(route, {field: value})
                        self.assertEqual(response.status_code, 400, response.data)
                        self.assertIn(field, response.data["errors"])

    def test_read_does_not_mutate_domain_and_detail_has_no_write_methods(self):
        before = order_domain_snapshot()
        self.client.get("/api/orders/")
        self.client.get(f"/api/orders/{self.own.pk}/")
        for method in (self.client.post, self.client.patch, self.client.put, self.client.delete):
            response = method(f"/api/orders/{self.own.pk}/", {}, format="json")
            self.assertIn(response.status_code, (403, 405))
        self.assertEqual(order_domain_snapshot(), before)

    def test_list_queries_do_not_grow_per_order(self):
        self.auth(self.admin)
        with CaptureQueriesContext(connection) as first:
            self.assertEqual(self.client.get("/api/orders/").status_code, 200)
        for _ in range(5):
            create_order(
                user=self.user,
                items=[{"product_id": self.second.pk, "quantity": 1}],
                shipping_address=ADDRESS,
            )
        with CaptureQueriesContext(connection) as second:
            response = self.client.get("/api/orders/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 7)
        self.assertEqual(len(first), len(second))
        self.assertLessEqual(len(second), 6)

    def test_errors_have_consistent_envelope_and_no_internal_diagnostics(self):
        responses = [
            self.client.post("/api/orders/", {}, format="json"),
            self.client.get("/api/orders/?ordering=?"),
            self.client.get("/api/orders/999999/"),
            self.client.post("/api/orders/", "{bad", content_type="application/json"),
            self.client.post(
                "/api/orders/", "x=1", content_type="application/x-www-form-urlencoded"
            ),
        ]
        self.client.credentials()
        responses.append(self.client.get("/api/orders/"))
        for response in responses:
            self.assertGreaterEqual(response.status_code, 400)
            self.assertEqual(set(response.data), {"code", "detail", "errors"})
            self.assertIn("no-store", response["Cache-Control"])
            self.assertNotIn("Traceback", str(response.data))

    def test_unknown_api_routes_also_return_private_json_error(self):
        for path in ("/api/missing/", "/api/products/-1/", "/api/stock/-1/", "/api/orders/-1/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response["Content-Type"], "application/json")
            self.assertEqual(set(response.json()), {"code", "detail", "errors"})
            self.assertIn("no-store", response["Cache-Control"])

    def test_openapi_validates_and_documents_only_implemented_routes(self):
        schema = SchemaGenerator().get_schema(public=True)
        validate_schema(schema)
        paths = schema["paths"]
        for path in (
            "/api/auth/register/",
            "/api/auth/token/",
            "/api/auth/token/refresh/",
            "/api/auth/me/",
            "/api/products/",
            "/api/products/{product_id}/",
            "/api/stock/",
            "/api/stock/{product_id}/movements/",
            "/api/stock/movements/",
            "/api/orders/",
            "/api/orders/{order_id}/",
            "/api/orders/{order_id}/simulated-payment/",
            "/api/orders/{order_id}/cancel/",
            "/api/orders/{order_id}/ship/",
            "/api/orders/{order_id}/deliver/",
        ):
            self.assertIn(path, paths)
        self.assertFalse(any("report" in path for path in paths))
        for path, methods in paths.items():
            for name, operation in methods.items():
                self.assertIn("Perfil autorizado:", operation["description"], (path, name))
                self.assertIn("400", operation["responses"])
                self.assertIn("403", operation["responses"])
                self.assertIn("409", operation["responses"])
        self.assertIn("get", paths["/api/orders/"])
        self.assertIn("post", paths["/api/orders/"])
        self.assertEqual(schema["components"]["securitySchemes"]["jwtAuth"]["scheme"], "bearer")
        self.assertIn(
            "SIMULADO", paths["/api/orders/{order_id}/simulated-payment/"]["post"]["summary"]
        )

    def test_swagger_schema_and_local_assets_work_without_auth_or_external_cdn(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-stale-token")
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("SwaggerUIBundle", html)
        self.assertIn('"persistAuthorization": false', html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertEqual(self.client.get("/api/schema/?format=json").status_code, 200)
        for name in (
            "swagger-ui.css",
            "swagger-ui-bundle.js",
            "swagger-ui-standalone-preset.js",
            "favicon-32x32.png",
        ):
            response = self.client.get(f"/static/drf_spectacular_sidecar/swagger-ui-dist/{name}")
            self.assertEqual(response.status_code, 200, name)
            response.close()
        self.assertEqual(self.client.get("/static/../../.env").status_code, 404)
