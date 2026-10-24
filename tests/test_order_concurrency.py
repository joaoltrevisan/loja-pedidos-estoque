from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Sum
from django.test import TransactionTestCase, override_settings

from catalog.models import Product
from inventory.models import Stock, StockMovement
from orders.exceptions import OrderConflict
from orders.models import Order, OrderItem
from orders.services import create_order
from tests.concurrency import ControlledConcurrencyMixin
from tests.order_fixtures import ADDRESS, build_order_fixtures
from tests.test_authentication import TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class OrderConcurrencyTests(ControlledConcurrencyMixin, TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        build_order_fixtures(self)

    def purchase(self, user, items=None):
        try:
            order = create_order(
                user=user,
                items=items or [{"product_id": self.product.pk, "quantity": 1}],
                shipping_address=dict(ADDRESS),
            )
            return "created", order.pk
        except OrderConflict as error:
            return "conflict", error.code

    def set_available(self, product, quantity):
        with transaction.atomic():
            stock = Stock.objects.select_for_update().get(product=product)
            delta = quantity - stock.available_quantity
            stock.available_quantity = quantity
            stock.save()
            if delta:
                StockMovement.objects.create(
                    product=product,
                    performed_by=self.admin,
                    movement_type="ADJUSTMENT",
                    quantity_delta=delta,
                    reason="Cenario ficticio de teste",
                )

    def assert_ledger(self):
        for stock in Stock.objects.all():
            self.assertEqual(
                stock.available_quantity,
                StockMovement.objects.filter(product_id=stock.product_id).aggregate(
                    total=Sum("quantity_delta")
                )["total"],
            )

    def test_two_customers_dispute_last_unit_and_second_rechecks_after_wait(self):
        self.set_available(self.product, 1)
        first, second = self.run_contended(
            lambda *_: self.purchase(self.user),
            lambda *_: self.purchase(self.other),
            pause_first_insert=True,
        )
        self.assertEqual(first[0], "created")
        self.assertEqual(second, ("conflict", "insufficient_stock"))
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 0)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)
        self.assert_ledger()

    def test_reversed_multi_product_requests_use_common_lock_order(self):
        self.set_available(self.product, 2)
        self.set_available(self.second, 2)
        items = [
            {"product_id": self.product.pk, "quantity": 1},
            {"product_id": self.second.pk, "quantity": 1},
        ]
        results = self.run_contended(
            lambda *_: self.purchase(self.user, items),
            lambda *_: self.purchase(self.other, list(reversed(items))),
            pause_first_insert=True,
        )
        self.assertEqual([result[0] for result in results], ["created", "created"])
        self.assertEqual(OrderItem.objects.count(), 4)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 4)
        self.assertEqual(list(Stock.objects.values_list("available_quantity", flat=True)), [0, 0])
        self.assert_ledger()

    def test_rollback_releases_locks_and_waiting_buyer_can_reserve(self):
        self.set_available(self.product, 1)

        def first_operation(*_):
            def fail_after_ledger(execute, sql, params, many, context):
                result = execute(sql, params, many, context)
                if sql.startswith('INSERT INTO "inventory_stockmovement"'):
                    raise RuntimeError("Falha controlada depois de gravar a reserva")
                return result

            with connection.execute_wrapper(fail_after_ledger):
                try:
                    self.purchase(self.user)
                except RuntimeError:
                    return "rolled_back", None
            raise AssertionError("Falha controlada nao ocorreu")

        first, second = self.run_contended(
            first_operation, lambda *_: self.purchase(self.other), pause_first_insert=True
        )
        self.assertEqual(first[0], "rolled_back")
        self.assertEqual(second[0], "created")
        self.assertEqual(Order.objects.get().customer.user_id, self.other.pk)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(StockMovement.objects.filter(movement_type="RESERVATION").count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 0)
        self.assert_ledger()

    def product_change(self, changes, *, hold=False):
        def operation(locked, release):
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=self.product.pk)
                for key, value in changes.items():
                    setattr(product, key, value)
                product.save(update_fields=[*changes, "updated_at"])
                if hold:
                    locked.set()
                    if not release.wait(5):
                        raise TimeoutError("Teste nao liberou a alteracao de produto")
            return "updated", product.pk

        return operation

    def test_price_update_first_makes_waiting_purchase_use_new_price(self):
        _, second = self.run_contended(
            self.product_change({"price": Decimal("30.00")}, hold=True),
            lambda *_: self.purchase(self.user),
        )
        self.assertEqual(second[0], "created")
        self.assertEqual(Order.objects.get().total, Decimal("30.00"))
        self.assertEqual(OrderItem.objects.get().unit_price, Decimal("30.00"))
        self.assert_ledger()

    def test_purchase_first_preserves_old_price_and_next_purchase_uses_new_price(self):
        first, _ = self.run_contended(
            lambda *_: self.purchase(self.user),
            self.product_change({"price": Decimal("30.00")}),
            pause_first_insert=True,
        )
        self.assertEqual(Order.objects.get(pk=first[1]).total, Decimal("25.90"))
        self.assertEqual(OrderItem.objects.get(order_id=first[1]).unit_price, Decimal("25.90"))
        self.assertEqual(Product.objects.get(pk=self.product.pk).price, Decimal("30.00"))
        second = self.purchase(self.other)
        self.assertEqual(Order.objects.get(pk=second[1]).total, Decimal("30.00"))
        self.assert_ledger()

    def test_deactivation_first_rejects_waiting_purchase_without_reservation(self):
        _, second = self.run_contended(
            self.product_change({"is_active": False}, hold=True),
            lambda *_: self.purchase(self.user),
        )
        self.assertEqual(second, ("conflict", "product_inactive"))
        self.assertFalse(Order.objects.exists() or OrderItem.objects.exists())
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 10)
        self.assert_ledger()

    def test_purchase_waits_on_stock_row_before_writing_reservation(self):
        def stock_change(locked, release):
            with transaction.atomic():
                stock = Stock.objects.select_for_update().get(product=self.product)
                # Sonda de bloqueio: nao altera saldo nem grava FKs que precisem
                # adquirir o produto depois do estoque (ordem inversa ao contrato).
                locked.set()
                if not release.wait(5):
                    raise TimeoutError("Teste nao liberou o estoque")
            return "unlocked", stock.pk

        _, second = self.run_contended(
            stock_change, lambda *_: self.purchase(self.user), expect_stock_select=True
        )
        self.assertEqual(second[0], "created")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 9)
        self.assert_ledger()
