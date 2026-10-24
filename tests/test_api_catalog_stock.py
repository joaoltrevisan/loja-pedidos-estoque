import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from catalog.models import Product
from catalog.services import save_product
from common.limits import MAX_STOCK_QUANTITY
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.services import create_order
from tests.order_fixtures import ADDRESS, build_order_fixtures, order_domain_snapshot


class CatalogStockAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_order_fixtures(cls)

    def setUp(self):
        self.client = APIClient()
        self.auth(self.admin)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def product_payload(self, **changes):
        return {"sku": "API-NEW", "name": "Produto Ficticio", "price": "19.90", **changes}

    def movement(self, delta=3, kind="ENTRY", reason="Entrada ficticia.", **extra):
        return self.client.post(
            f"/api/stock/{self.product.pk}/movements/",
            {"movement_type": kind, "quantity_delta": delta, "reason": reason, **extra},
            format="json",
        )

    def assert_ledger(self):
        for stock in Stock.objects.all():
            total = (
                StockMovement.objects.filter(product_id=stock.product_id).aggregate(
                    n=Sum("quantity_delta")
                )["n"]
                or 0
            )
            self.assertEqual(stock.available_quantity, total)

    def test_product_creation_atomically_initializes_zero_stock(self):
        response = self.client.post("/api/products/", self.product_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data["id"])
        self.assertEqual(product.price, Decimal("19.90"))
        self.assertEqual(product.stock.available_quantity, 0)
        self.assertEqual(response.data["available_quantity"], 0)
        self.assertFalse(product.movements.exists())
        self.assert_ledger()

    def test_failed_stock_initialization_rolls_back_new_product(self):
        before = order_domain_snapshot()
        with (
            patch(
                "catalog.services.Stock.objects.create",
                side_effect=RuntimeError("Falha controlada"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.client.post("/api/products/", self.product_payload(), format="json")
        self.assertEqual(order_domain_snapshot(), before)

    def test_duplicate_sku_returns_conflict_without_partial_stock(self):
        before = order_domain_snapshot()
        response = self.client.post(
            "/api/products/", self.product_payload(sku=self.product.sku), format="json"
        )
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["code"], "sku_conflict")
        self.assertEqual(order_domain_snapshot(), before)
        response = self.client.patch(
            f"/api/products/{self.second.pk}/", {"sku": self.product.sku}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(order_domain_snapshot(), before)

    def test_product_rejects_invalid_money_types_precision_and_bounds(self):
        before = order_domain_snapshot()
        for price in (
            0,
            2.5,
            True,
            None,
            "0",
            "-1",
            "1.001",
            "100000000.00",
            "NaN",
            "Infinity",
            "abc",
        ):
            with self.subTest(price=price):
                response = self.client.post(
                    "/api/products/", self.product_payload(price=price), format="json"
                )
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data["code"], "validation_error")
                self.assertIn("price", response.data["errors"])
        self.assertEqual(order_domain_snapshot(), before)

    def test_product_text_boolean_limits_and_protected_fields(self):
        before = order_domain_snapshot()
        cases = (
            {"sku": "lower"},
            {"sku": "X" * 65},
            {"name": " "},
            {"name": 4},
            {"name": "X" * 201},
            {"description": "X" * 5001},
            {"is_active": "true"},
            {"is_active": 1},
            {"available_quantity": 4},
            {"id": 2},
            {"created_at": "2026-01-01"},
            {"name": "A\x00"},
            {"name": "A\ud800"},
        )
        for data in cases:
            with self.subTest(fields=tuple(data)):
                payload = json.dumps(self.product_payload(**data), ensure_ascii=True)
                response = self.client.post(
                    "/api/products/", payload, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(order_domain_snapshot(), before)

    def test_product_update_preserves_historical_order_and_stock(self):
        order = create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            shipping_address=ADDRESS,
        )
        response = self.client.patch(
            f"/api/products/{self.product.pk}/",
            {"price": "30.00", "sku": "NEW-SKU", "name": "Novo Nome"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        item = order.items.get()
        self.assertEqual(
            (item.product_sku, item.product_name, item.unit_price, order.total),
            ("ORDER-A", "Caderno Ficticio", Decimal("25.90"), Decimal("51.80")),
        )
        next_order = create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            shipping_address=ADDRESS,
        )
        self.assertEqual(next_order.total, Decimal("30.00"))
        self.assert_ledger()

    def test_customer_reads_active_only_admin_sees_inactive_and_can_reactivate(self):
        inactive = self.client.patch(
            f"/api/products/{self.product.pk}/", {"is_active": False}, format="json"
        )
        self.assertEqual(inactive.status_code, 200)
        self.assertEqual(self.client.get("/api/products/?is_active=false").data["count"], 1)
        self.auth(self.user)
        self.assertEqual(self.client.get("/api/products/").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/products/{self.product.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/products/?is_active=true").status_code, 403)
        self.auth(self.admin)
        self.assertEqual(self.client.get(f"/api/products/{self.product.pk}/").status_code, 200)
        self.assertEqual(
            self.client.patch(
                f"/api/products/{self.product.pk}/", {"is_active": True}, format="json"
            ).status_code,
            200,
        )

    def test_product_filters_ordering_and_deterministic_pagination(self):
        response = self.client.get("/api/products/?ordering=price&page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["id"], self.second.pk)
        self.assertIsNotNone(response.data["next"])
        next_page = self.client.get(response.data["next"])
        self.assertEqual(next_page.data["results"][0]["id"], self.product.pk)
        self.assertEqual(self.client.get("/api/products/?search=caderno").data["count"], 1)
        self.assertEqual(self.client.get("/api/products/?sku=ORDER-A").data["count"], 1)
        self.assertEqual(self.client.get("/api/products/?search=absent").data["results"], [])
        self.assertEqual(self.client.get("/api/products/?page=999").status_code, 404)

    def test_queries_reject_unknown_repeated_invalid_and_unsafe_ordering(self):
        for route in ("/api/products/", "/api/stock/", "/api/stock/movements/"):
            for query in (
                "page=0",
                "page=1.5",
                "page_size=101",
                "page_size=0",
                "page_size=1.5",
                "x=1",
                "page=1&page=2",
                "ordering=?",
                "ordering=product__price",
                "ordering=id,id",
                "ordering=--id",
                "ordering=id,-id,id,-id",
            ):
                with self.subTest(route=route, query=query):
                    response = self.client.get(route + "?" + query)
                    self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.client.get("/api/products/?is_active=1").status_code, 400)
        self.assertEqual(self.client.get("/api/products/?search=%00").status_code, 400)

    def test_catalog_and_stock_routes_enforce_current_roles(self):
        before = order_domain_snapshot()
        for user, expected in ((self.user, 403), (None, 401)):
            if user:
                self.auth(user)
            else:
                self.client.credentials()
            for route in ("/api/stock/", f"/api/stock/{self.product.pk}/", "/api/stock/movements/"):
                self.assertEqual(self.client.get(route).status_code, expected)
            self.assertEqual(self.movement().status_code, expected)
            self.assertEqual(
                self.client.post(
                    "/api/products/", self.product_payload(), format="json"
                ).status_code,
                expected,
            )
            self.assertEqual(
                self.client.patch(
                    f"/api/products/{self.product.pk}/", {"price": "1.00"}, format="json"
                ).status_code,
                expected,
            )
        self.assertEqual(self.client.get("/api/products/").status_code, 401)
        orphan = User.objects.create_user("unassigned@example.com", name="Ficticio")
        self.auth(orphan)
        self.assertEqual(self.client.get("/api/products/").status_code, 403)
        self.assertEqual(order_domain_snapshot(), before)

    def test_stock_entry_and_adjustment_record_actor_reason_and_balance(self):
        first = self.movement(5)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["stock"]["available_quantity"], 15)
        self.assertEqual(first.data["movement"]["performed_by_id"], self.admin.pk)
        self.assertIsNone(first.data["movement"]["order_id"])
        second = self.movement(-4, "ADJUSTMENT", " Correcao ficticia. ")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["stock"]["available_quantity"], 11)
        self.assertEqual(second.data["movement"]["reason"], "Correcao ficticia.")
        self.assert_ledger()

    def test_stock_rejects_invalid_delta_type_sign_limits_reason_and_mass_assignment(self):
        before = order_domain_snapshot()
        cases = [
            (q, "ENTRY", "Ficticio", {})
            for q in (0, -1, 1.0, 1.5, "1", True, None, MAX_STOCK_QUANTITY + 1)
        ]
        cases += [
            (0, "ADJUSTMENT", "Ficticio", {}),
            (1, "RESERVATION", "Ficticio", {}),
            (1, "RELEASE", "Ficticio", {}),
        ]
        cases += [(1, "ENTRY", r, {}) for r in ("", " ", "x" * 501, None, 12)]
        cases += [
            (1, "ENTRY", "Ficticio", {key: 1})
            for key in ("performed_by_id", "order_id", "available_quantity", "created_at")
        ]
        for delta, kind, reason, extra in cases:
            with self.subTest(delta=delta, kind=kind, extra=extra):
                response = self.movement(delta, kind, reason, **extra)
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(order_domain_snapshot(), before)

    def test_stock_negative_and_overflow_results_conflict_without_partial_writes(self):
        before = order_domain_snapshot()
        for delta, kind in ((-11, "ADJUSTMENT"), (MAX_STOCK_QUANTITY, "ENTRY")):
            response = self.movement(delta, kind)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "stock_limit_exceeded")
            self.assertEqual(order_domain_snapshot(), before)
        self.assertEqual(self.movement(-10, "ADJUSTMENT").status_code, 201)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 0)
        self.assert_ledger()

    def test_movement_write_failure_rolls_back_balance(self):
        before = order_domain_snapshot()
        original = StockMovement.objects.create

        def fail(**kwargs):
            original(**kwargs)
            self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 13)
            raise RuntimeError("Falha controlada apos gravar movimento")

        with (
            patch("inventory.services.StockMovement.objects.create", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.movement()
        self.assertEqual(order_domain_snapshot(), before)

    def test_stock_audit_filters_and_read_only_methods(self):
        self.movement(4)
        self.movement(-2, "ADJUSTMENT")
        url = (
            f"/api/stock/movements/?product_id={self.product.pk}"
            "&movement_type=ADJUSTMENT&ordering=-created_at"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["quantity_delta"], -2)
        self.assertEqual(self.client.get("/api/stock/?max_quantity=12").data["count"], 1)
        self.assertEqual(
            self.client.get(f"/api/stock/?product_id={self.second.pk}").data["count"], 1
        )
        for route in ("/api/stock/", f"/api/stock/{self.product.pk}/", "/api/stock/movements/"):
            self.assertEqual(self.client.patch(route, {}, format="json").status_code, 405)
            self.assertEqual(self.client.delete(route).status_code, 405)
        self.assertEqual(self.client.delete(f"/api/products/{self.product.pk}/").status_code, 405)

    def test_missing_and_oversized_ids_never_trigger_database_overflow(self):
        for product_id in (0, 99999999, 9223372036854775808, 10**100):
            for route in (f"/api/products/{product_id}/", f"/api/stock/{product_id}/"):
                self.assertEqual(self.client.get(route).status_code, 404)
            response = self.client.post(
                f"/api/stock/{product_id}/movements/",
                {"movement_type": "ENTRY", "quantity_delta": 1, "reason": "Ficticio"},
                format="json",
            )
            self.assertEqual(response.status_code, 404)
        Stock.objects.filter(product=self.product).delete()
        self.assertEqual(self.movement().status_code, 409)

    def test_direct_services_revalidate_role_and_input(self):
        before = order_domain_snapshot()
        for user in (None, AnonymousUser(), self.user):
            with self.assertRaises(PermissionDenied):
                save_product(user=user, data=self.product_payload())
            with self.assertRaises(PermissionDenied):
                change_stock(
                    user=user,
                    product_id=self.product.pk,
                    movement_type="ENTRY",
                    quantity_delta=1,
                    reason="Ficticio",
                )
        for data in (
            self.product_payload(price=1.5),
            self.product_payload(price="NaN"),
            self.product_payload(price="1.001"),
            self.product_payload(sku="lower"),
            {"available_quantity": 5},
        ):
            with self.assertRaises(ValidationError):
                save_product(user=self.admin, data=data)
        for delta in (True, "1", Decimal("1"), 0, MAX_STOCK_QUANTITY + 1):
            with self.assertRaises(ValidationError):
                change_stock(
                    user=self.admin,
                    product_id=self.product.pk,
                    movement_type="ENTRY",
                    quantity_delta=delta,
                    reason="Ficticio",
                )
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            save_product(user=self.admin, data=self.product_payload())
        with self.assertRaises(PermissionDenied):
            change_stock(
                user=self.admin,
                product_id=self.product.pk,
                movement_type="ENTRY",
                quantity_delta=1,
                reason="Ficticio",
            )
        self.assertEqual(order_domain_snapshot(), before)
