import json
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Customer, User
from catalog.models import Product
from inventory.models import Stock, StockMovement
from orders.models import Order, OrderItem, Shipment, SimulatedPayment
from orders.services import create_order
from tests.order_fixtures import ADDRESS, build_order_fixtures
from tests.test_authentication import TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class OrderCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_order_fixtures(cls)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.authenticate(self.user)

    def authenticate(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def payload(self):
        return {
            "items": [{"product_id": self.product.pk, "quantity": 3}],
            "shipping_address": deepcopy(ADDRESS),
        }

    def post(self, payload=None):
        return self.client.post(
            "/api/orders/", self.payload() if payload is None else payload, format="json"
        )

    def snapshot(self):
        return {
            "orders": list(Order.objects.order_by("pk").values()),
            "items": list(OrderItem.objects.order_by("pk").values()),
            "stocks": list(Stock.objects.order_by("pk").values()),
            "movements": list(StockMovement.objects.order_by("pk").values()),
            "payments": SimulatedPayment.objects.count(),
            "shipments": Shipment.objects.count(),
        }

    def assert_ledger(self):
        for stock in Stock.objects.all():
            self.assertEqual(
                stock.available_quantity,
                StockMovement.objects.filter(product_id=stock.product_id).aggregate(
                    total=Sum("quantity_delta")
                )["total"],
            )

    def test_create_reserves_stock_uses_server_values_and_records_actor(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get()
        item = order.items.get()
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.status, "PENDING_PAYMENT")
        self.assertEqual(order.total, Decimal("77.70"))
        self.assertEqual(order.currency, "BRL")
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assertEqual(
            (item.quantity, item.unit_price, item.product_sku, item.product_name),
            (3, Decimal("25.90"), self.product.sku, self.product.name),
        )
        movement = order.stock_movements.get()
        self.assertEqual(movement.quantity_delta, -3)
        self.assertEqual(movement.movement_type, "RESERVATION")
        self.assertEqual(movement.performed_by_id, self.user.pk)
        self.assertTrue(movement.reason.strip())
        self.assertEqual(response.data["total"], "77.70")
        self.assertEqual(response.data["items"][0]["subtotal"], "77.70")
        self.assertEqual(response.data["payment_mode"], "SIMULATED_NO_REAL_CHARGE")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(SimulatedPayment.objects.exists() or Shipment.objects.exists())
        self.assertIsNone(order.paid_at)
        self.assert_ledger()

    def test_multiple_products_decimal_total_and_deterministic_item_order(self):
        data = self.payload()
        data["items"] = [
            {"product_id": self.second.pk, "quantity": 3},
            {"product_id": self.product.pk, "quantity": 2},
        ]
        response = self.post(data)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "52.10")
        self.assertEqual(
            [item["product_id"] for item in response.data["items"]],
            [self.product.pk, self.second.pk],
        )
        self.assertEqual(OrderItem.objects.count(), 2)
        self.assertEqual(Order.objects.get().stock_movements.count(), 2)
        self.assert_ledger()

    def test_input_shapes_empty_repeated_and_quantity_types_leave_no_changes(self):
        before = self.snapshot()
        invalid = [
            None,
            {},
            "items",
            [],
            [None],
            ["item"],
            [{"product_id": self.product.pk}],
            [{"product_id": self.product.pk, "quantity": 1}] * 2,
        ]
        invalid += [
            [{"product_id": self.product.pk, "quantity": quantity}]
            for quantity in (0, -1, 1.5, 1.0, True, False, "1", None, 10000)
        ]
        invalid += [
            [{"product_id": product_id, "quantity": 1}]
            for product_id in (0, -1, True, 1.0, "1", None, 9223372036854775808)
        ]
        for items in invalid:
            with self.subTest(items=items):
                data = self.payload()
                data["items"] = items
                self.assertEqual(self.post(data).status_code, 400)
                self.assertEqual(self.snapshot(), before)

    def test_rejects_more_than_100_lines_before_reserving(self):
        data = self.payload()
        data["items"] *= 101
        before = self.snapshot()
        self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_accepts_100_distinct_products(self):
        products = Product.objects.bulk_create(
            [Product(sku=f"LIMIT-{i}", name="Ficticio", price=Decimal("0.01")) for i in range(100)]
        )
        Stock.objects.bulk_create([Stock(product=p, available_quantity=1) for p in products])
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    product=p,
                    performed_by=self.admin,
                    movement_type="ENTRY",
                    quantity_delta=1,
                    reason="Entrada ficticia de teste",
                )
                for p in products
            ]
        )
        data = self.payload()
        data["items"] = [{"product_id": p.pk, "quantity": 1} for p in reversed(products)]
        response = self.post(data)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "1.00")
        self.assertEqual(Order.objects.get().items.count(), 100)
        self.assert_ledger()

    def test_accepts_maximum_item_quantity_when_stock_covers_it(self):
        Stock.objects.filter(product=self.product).update(available_quantity=9999)
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.admin,
            movement_type="ADJUSTMENT",
            quantity_delta=9989,
            reason="Ajuste ficticio de teste",
        )
        data = self.payload()
        data["items"][0]["quantity"] = 9999
        response = self.post(data)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "258974.10")
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 0)
        self.assert_ledger()

    def test_rejects_owner_price_total_status_and_privileges(self):
        before = self.snapshot()
        for field in (
            "id",
            "customer_id",
            "customer",
            "user",
            "total",
            "status",
            "currency",
            "paid_at",
            "created_at",
            "is_staff",
            "simulated_payment",
        ):
            with self.subTest(field=field):
                data = self.payload()
                data[field] = self.other.pk
                response = self.post(data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data["errors"])
        self.assertEqual(self.snapshot(), before)

    def test_rejects_protected_item_fields(self):
        before = self.snapshot()
        for field in ("unit_price", "price", "total", "product_sku", "product_name", "order", "id"):
            with self.subTest(field=field):
                data = self.payload()
                data["items"][0][field] = "0.01"
                self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_missing_products_in_multi_item_purchase_never_reserve_partially(self):
        data = self.payload()
        data["items"].append({"product_id": 9223372036854775807, "quantity": 1})
        before = self.snapshot()
        self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_inactive_product_rejects_entire_purchase(self):
        Product.objects.filter(pk=self.second.pk).update(is_active=False)
        data = self.payload()
        data["items"].append({"product_id": self.second.pk, "quantity": 1})
        before = self.snapshot()
        response = self.post(data)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "product_inactive")
        self.assertEqual(self.snapshot(), before)

    def test_insufficient_stock_rejects_entire_purchase(self):
        data = self.payload()
        data["items"].append({"product_id": self.second.pk, "quantity": 21})
        before = self.snapshot()
        response = self.post(data)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "insufficient_stock")
        self.assertEqual(self.snapshot(), before)

    def test_missing_stock_is_not_silently_created(self):
        Stock.objects.filter(product=self.second).delete()
        data = self.payload()
        data["items"].append({"product_id": self.second.pk, "quantity": 1})
        before = self.snapshot()
        response = self.post(data)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "stock_unavailable")
        self.assertEqual(self.snapshot(), before)

    def test_required_address_fields_types_formats_and_limits(self):
        before = self.snapshot()
        invalid_addresses = [
            None,
            [],
            "address",
            {},
            dict(ADDRESS, country="US"),
            dict(ADDRESS, state="XX"),
            dict(ADDRESS, state="sp"),
            dict(ADDRESS, postal_code="01001-000"),
            dict(ADDRESS, postal_code="１２３４５６７８"),
        ]
        for key in ADDRESS:
            missing = dict(ADDRESS)
            del missing[key]
            invalid_addresses.append(missing)
            invalid_addresses += [dict(ADDRESS, **{key: value}) for value in (" ", None, 123)]
            limit = Order._meta.get_field(f"shipping_{key}").max_length
            invalid_addresses.append(dict(ADDRESS, **{key: "x" * (limit + 1)}))
        invalid_addresses.append(dict(ADDRESS, complement="x" * 101))
        for address in invalid_addresses:
            with self.subTest(address=address):
                data = self.payload()
                data["shipping_address"] = address
                self.assertEqual(self.post(data).status_code, 400)
                self.assertEqual(self.snapshot(), before)

    def test_address_is_trimmed_and_saved_as_independent_snapshot(self):
        data = self.payload()
        data["shipping_address"]["recipient"] = " Destinatario Ficticio "
        data["shipping_address"]["complement"] = " Bloco Modelo "
        response = self.post(data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["shipping_address"]["recipient"], "Destinatario Ficticio")
        self.assertEqual(response.data["shipping_address"]["complement"], "Bloco Modelo")
        self.assertEqual(response.data["shipping_address"]["country"], "BR")
        User.objects.filter(pk=self.user.pk).update(name="Outro nome")
        self.assertEqual(Order.objects.get().shipping_recipient, "Destinatario Ficticio")

    def test_address_rejects_null_and_unpaired_surrogate_characters(self):
        before = self.snapshot()
        for character in ("\x00", "\ud800", "\udfff"):
            with self.subTest(character=repr(character)):
                data = self.payload()
                data["shipping_address"]["recipient"] = "Ficticio" + character
                # Escapes ASCII permitem enviar ate um surrogate invalido no JSON.
                response = self.client.post(
                    "/api/orders/",
                    json.dumps(data, ensure_ascii=True).encode("ascii"),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.snapshot(), before)

    def test_anonymous_admin_and_missing_profile_cannot_create(self):
        before = self.snapshot()
        self.client.credentials()
        self.assertEqual(self.post().status_code, 401)
        self.authenticate(self.admin)
        self.assertEqual(self.post().status_code, 403)
        Customer.objects.create(user=self.admin)
        self.assertEqual(self.post().status_code, 403)
        orphan = User.objects.create_user("semperfil@example.com", name="Ficticio")
        self.authenticate(orphan)
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_service_rechecks_current_role_even_with_stale_user_object(self):
        before = self.snapshot()
        for changes in ({"is_staff": True}, {"is_staff": False, "is_active": False}):
            User.objects.filter(pk=self.user.pk).update(**changes)
            with self.assertRaises(PermissionDenied):
                create_order(user=self.user, **self.payload())
        for user in (AnonymousUser(), self.admin, None):
            with self.assertRaises(PermissionDenied):
                create_order(user=user, **self.payload())
        self.assertEqual(self.snapshot(), before)

    def test_service_revalidates_inputs_for_non_http_callers(self):
        before = self.snapshot()
        for quantity in (Decimal("1"), True, 1.0, "1", -1):
            data = self.payload()
            data["items"][0]["quantity"] = quantity
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                create_order(user=self.user, **data)
        data = self.payload()
        data["shipping_address"]["country"] = "US"
        with self.assertRaises(ValidationError):
            create_order(user=self.user, **data)
        self.assertEqual(self.snapshot(), before)

    def test_failure_after_all_writes_rolls_back_order_items_balances_and_ledger(self):
        before = self.snapshot()
        original = StockMovement.objects.bulk_create

        def fail_after_writes(objects, **kwargs):
            original(objects, **kwargs)
            self.assertEqual(Order.objects.count(), 1)
            self.assertEqual(OrderItem.objects.count(), 2)
            self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
            self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 2)
            raise RuntimeError("Falha controlada apos todas as gravacoes")

        data = self.payload()
        data["items"].append({"product_id": self.second.pk, "quantity": 2})
        with patch(
            "orders.services.StockMovement.objects.bulk_create", side_effect=fail_after_writes
        ):
            with self.assertRaisesMessage(RuntimeError, "Falha controlada"):
                self.post(data)
        self.assertEqual(self.snapshot(), before)
        self.assert_ledger()

    def test_catalog_changes_do_not_rewrite_old_snapshots(self):
        first = self.post()
        self.assertEqual(first.status_code, 201)
        Product.objects.filter(pk=self.product.pk).update(
            price=Decimal("30.00"), sku="NEW-ORDER-A", name="Novo nome"
        )
        second = self.post()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["total"], "90.00")
        old = OrderItem.objects.get(order_id=first.data["id"])
        self.assertEqual(
            (old.unit_price, old.product_sku, old.product_name),
            (Decimal("25.90"), "ORDER-A", "Caderno Ficticio"),
        )
        self.assertEqual(Order.objects.get(pk=first.data["id"]).total, Decimal("77.70"))
        self.assertEqual(second.data["items"][0]["product_sku"], "NEW-ORDER-A")
        self.assert_ledger()

    def test_repeated_creation_is_two_orders_and_two_reservations(self):
        first, second = self.post(), self.post()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.data["id"], second.data["id"])
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 4)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 2)
        self.assert_ledger()

    def test_creation_rejects_unsupported_write_methods_and_bad_json(self):
        before = self.snapshot()
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method("/api/orders/").status_code, 405)
        self.assertEqual(self.client.get("/api/orders/1/").status_code, 404)
        self.assertEqual(self.client.post("/api/orders/", [], format="json").status_code, 400)
        self.assertEqual(
            self.client.post("/api/orders/", "{bad", content_type="application/json").status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/orders/", "x=1", content_type="application/x-www-form-urlencoded"
            ).status_code,
            415,
        )
        self.assertEqual(self.snapshot(), before)
