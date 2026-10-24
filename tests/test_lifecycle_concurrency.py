from django.db import connection
from django.db.models import Sum
from django.test import TransactionTestCase, override_settings

from inventory.models import Stock, StockMovement
from orders.exceptions import OrderConflict
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order, Shipment, SimulatedPayment
from orders.services import create_order
from tests.concurrency import ControlledConcurrencyMixin
from tests.order_fixtures import ADDRESS, build_order_fixtures
from tests.test_authentication import TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class LifecycleConcurrencyTests(ControlledConcurrencyMixin, TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        build_order_fixtures(self)
        self.order = create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": 3}],
            shipping_address=dict(ADDRESS),
        )

    def pay(self):
        return approve_simulated_payment(user=self.admin, order_id=self.order.pk)

    def cancel(self):
        return cancel_order(user=self.user, order_id=self.order.pk)

    def ship(self, tracking="SIMULATED-001"):
        return ship_order(user=self.admin, order_id=self.order.pk, tracking_code=tracking)

    def deliver(self):
        return deliver_order(user=self.admin, order_id=self.order.pk)

    def race(self, first_action, second_action):
        def capture(action):
            def operation(*_):
                try:
                    return "ok", action()
                except OrderConflict as error:
                    return "conflict", error.code

            return operation

        return self.run_contended(
            capture(first_action),
            capture(second_action),
            pause_before=lambda sql: sql.startswith('UPDATE "orders_order"'),
        )

    def assert_ledger(self):
        for stock in Stock.objects.all():
            self.assertEqual(
                stock.available_quantity,
                stock.product.movements.aggregate(total=Sum("quantity_delta"))["total"],
            )

    def test_payment_first_prevents_waiting_cancellation(self):
        first, second = self.race(self.pay, self.cancel)
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "invalid_transition"))
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "PAID")
        self.assertEqual(SimulatedPayment.objects.count(), 1)
        self.assertFalse(StockMovement.objects.filter(movement_type="RELEASE").exists())
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assert_ledger()

    def test_cancellation_first_prevents_waiting_payment(self):
        first, second = self.race(self.cancel, self.pay)
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "invalid_transition"))
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "CANCELLED")
        self.assertFalse(SimulatedPayment.objects.exists())
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 10)
        self.assertEqual(StockMovement.objects.filter(movement_type="RELEASE").count(), 1)
        self.assert_ledger()

    def test_two_payment_confirmations_preserve_one_reference_and_date(self):
        first, second = self.race(self.pay, self.pay)
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        left, right = first[1], second[1]
        self.assertEqual(left.simulated_payment.pk, right.simulated_payment.pk)
        self.assertEqual(left.simulated_payment.reference, right.simulated_payment.reference)
        self.assertEqual(left.order.paid_at, right.order.paid_at)
        self.assertEqual(left.order.updated_at, right.order.updated_at)
        self.assertEqual(SimulatedPayment.objects.count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assert_ledger()

    def test_two_cancellations_release_only_once(self):
        first, second = self.race(self.cancel, self.cancel)
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(first[1].order.cancelled_at, second[1].order.cancelled_at)
        self.assertEqual(first[1].order.updated_at, second[1].order.updated_at)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 10)
        self.assertEqual(StockMovement.objects.filter(movement_type="RELEASE").count(), 1)
        self.assert_ledger()

    def test_two_shipments_keep_original_record_and_dates(self):
        self.pay()
        first, second = self.race(self.ship, self.ship)
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(first[1].shipment.pk, second[1].shipment.pk)
        self.assertEqual(first[1].shipment.shipped_at, second[1].shipment.shipped_at)
        self.assertEqual(first[1].order.updated_at, second[1].order.updated_at)
        self.assertEqual(Shipment.objects.count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assert_ledger()

    def test_two_deliveries_keep_original_record_and_dates(self):
        self.pay()
        self.ship()
        first, second = self.race(self.deliver, self.deliver)
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(first[1].shipment.pk, second[1].shipment.pk)
        self.assertEqual(first[1].shipment.delivered_at, second[1].shipment.delivered_at)
        self.assertEqual(first[1].order.updated_at, second[1].order.updated_at)
        self.assertEqual(Shipment.objects.count(), 1)
        self.assert_ledger()

    def test_waiting_delivery_observes_completed_shipping(self):
        self.pay()
        first, second = self.race(self.ship, self.deliver)
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(first[1].order.status, "SHIPPED")
        self.assertIsNone(first[1].shipment.delivered_at)
        self.assertEqual(second[1].order.status, "DELIVERED")
        self.assertEqual(second[1].shipment.shipped_at, first[1].shipment.shipped_at)
        self.assertEqual(Shipment.objects.count(), 1)
        self.assert_ledger()

    def test_conflicting_simultaneous_tracking_is_rejected(self):
        self.pay()
        first, second = self.race(self.ship, lambda: self.ship("SIMULATED-OTHER"))
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "tracking_conflict"))
        self.assertEqual(Shipment.objects.get().tracking_code, "SIMULATED-001")
        self.assert_ledger()

    def test_cancellation_and_waiting_new_purchase_preserve_stock_and_ledger(self):
        Stock.objects.filter(product=self.product).update(available_quantity=0)
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.admin,
            movement_type="ADJUSTMENT",
            quantity_delta=-7,
            reason="Cenario ficticio de concorrencia",
        )
        first, second = self.race(
            self.cancel,
            lambda: create_order(
                user=self.other,
                items=[{"product_id": self.product.pk, "quantity": 3}],
                shipping_address=dict(ADDRESS),
            ),
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 0)
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(StockMovement.objects.filter(movement_type="RELEASE").count(), 1)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 2)
        self.assert_ledger()

    def test_cancellation_rollback_allows_waiting_payment_without_release(self):
        def fail_cancel():
            def fail_after_order_save(execute, sql, params, many, context):
                result = execute(sql, params, many, context)
                if sql.startswith('UPDATE "orders_order"'):
                    raise RuntimeError("Falha controlada depois de gravar cancelamento")
                return result

            with connection.execute_wrapper(fail_after_order_save):
                try:
                    self.cancel()
                except RuntimeError as error:
                    self.assertIn("Falha controlada", str(error))
                    return "rolled_back"
            raise AssertionError("Falha esperada nao aconteceu")

        first, second = self.race(fail_cancel, self.pay)
        self.assertEqual(first, ("ok", "rolled_back"))
        self.assertEqual(second[0], "ok")
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "PAID")
        self.assertEqual(SimulatedPayment.objects.count(), 1)
        self.assertFalse(StockMovement.objects.filter(movement_type="RELEASE").exists())
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assert_ledger()

    def test_two_multi_product_cancellations_follow_common_product_order(self):
        items = [
            {"product_id": self.product.pk, "quantity": 1},
            {"product_id": self.second.pk, "quantity": 2},
        ]
        other_order = create_order(user=self.other, items=items, shipping_address=dict(ADDRESS))
        own_order = create_order(
            user=self.user, items=list(reversed(items)), shipping_address=dict(ADDRESS)
        )
        first, second = self.race(
            lambda: cancel_order(user=self.other, order_id=other_order.pk),
            lambda: cancel_order(user=self.user, order_id=own_order.pk),
        )
        self.assertEqual([first[0], second[0]], ["ok", "ok"])
        self.assertEqual(StockMovement.objects.filter(movement_type="RELEASE").count(), 4)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assertEqual(Stock.objects.get(product=self.second).available_quantity, 20)
        self.assert_ledger()
