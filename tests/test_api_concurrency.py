from django.core.cache import cache
from django.db import connection
from django.db.models import Sum
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.integrity import inspect_order_history
from orders.models import Order, OrderItem, SimulatedPayment
from orders.services import create_order
from tests.concurrency import ControlledConcurrencyMixin
from tests.order_fixtures import ADDRESS, build_order_fixtures
from tests.test_authentication import TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class APIConcurrencyTests(ControlledConcurrencyMixin, TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        cache.clear()
        build_order_fixtures(self)
        self.tokens = {
            u.pk: str(AccessToken.for_user(u)) for u in (self.user, self.other, self.admin)
        }

    def post_operation(self, user, path, payload):
        def operation(*_):
            # Cliente independente por requisicao, sem compartilhar credenciais mutaveis.
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens[user.pk]}")
            response = client.post(path, payload, format="json")
            self.assertIn("no-store", response["Cache-Control"])
            return response.status_code, response.json()

        return operation

    def assert_integrity(self):
        for stock in Stock.objects.all():
            balance = stock.product.movements.aggregate(total=Sum("quantity_delta"))["total"]
            self.assertEqual(stock.available_quantity, balance)
        for order in Order.objects.select_related("customer"):
            inspect_order_history(order)

    def test_http_customers_dispute_last_unit_with_one_created_and_one_conflict(self):
        change_stock(
            user=self.admin,
            product_id=self.product.pk,
            movement_type="ADJUSTMENT",
            quantity_delta=-9,
            reason="Ultima unidade ficticia de teste.",
        )
        payload = {
            "items": [{"product_id": self.product.pk, "quantity": 1}],
            "shipping_address": dict(ADDRESS),
        }
        first, second = self.run_contended(
            self.post_operation(self.user, "/api/orders/", payload),
            self.post_operation(self.other, "/api/orders/", payload),
            pause_first_insert=True,
        )
        self.assertEqual(first[0], 201, first[1])
        self.assertEqual(first[1]["payment_mode"], "SIMULATED_NO_REAL_CHARGE")
        self.assertEqual(second[0], 409, second[1])
        self.assertEqual(second[1]["code"], "insufficient_stock")
        self.assertEqual(Order.objects.get().customer.user_id, self.user.pk)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 0)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)
        self.assertFalse(SimulatedPayment.objects.exists())
        self.assert_integrity()

    def payment_cancel_race(self, *, payment_first):
        order = create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": 3}],
            shipping_address=dict(ADDRESS),
        )
        pay = self.post_operation(self.admin, f"/api/orders/{order.pk}/simulated-payment/", {})
        cancel = self.post_operation(self.user, f"/api/orders/{order.pk}/cancel/", {})
        first, second = self.run_contended(
            pay if payment_first else cancel,
            cancel if payment_first else pay,
            pause_before=lambda sql: sql.startswith('UPDATE "orders_order"'),
        )
        self.assertEqual(first[0], 200, first[1])
        self.assertEqual(second[0], 409, second[1])
        self.assertEqual(second[1]["code"], "invalid_transition")
        order.refresh_from_db()
        self.assertEqual(order.status, "PAID" if payment_first else "CANCELLED")
        self.assertEqual(SimulatedPayment.objects.count(), 1 if payment_first else 0)
        self.assertEqual(
            Stock.objects.get(product=self.product).available_quantity, 7 if payment_first else 10
        )
        self.assertEqual(
            StockMovement.objects.filter(movement_type="RELEASE").count(), 0 if payment_first else 1
        )
        self.assert_integrity()

    def test_http_payment_first_rejects_waiting_cancellation(self):
        self.payment_cancel_race(payment_first=True)

    def test_http_cancellation_first_rejects_waiting_payment(self):
        self.payment_cancel_race(payment_first=False)
