from decimal import Decimal

from django.db.models import Sum
from django.test import TransactionTestCase

from catalog.models import Product
from catalog.services import save_product
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.exceptions import OrderConflict
from orders.lifecycle import cancel_order
from orders.models import Order
from orders.services import create_order
from tests.concurrency import ControlledConcurrencyMixin
from tests.order_fixtures import ADDRESS, build_order_fixtures


class CatalogStockConcurrencyTests(ControlledConcurrencyMixin, TransactionTestCase):
    def setUp(self):
        build_order_fixtures(self)

    def outcome(self, operation):
        try:
            result = operation()
            return ("ok", result.pk if hasattr(result, "pk") else result[0].available_quantity)
        except OrderConflict as error:
            return ("conflict", error.code)

    def buy(self, quantity=1):
        return create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": quantity}],
            shipping_address=ADDRESS,
        )

    def adjust(self, delta, kind="ADJUSTMENT"):
        return change_stock(
            user=self.admin,
            product_id=self.product.pk,
            movement_type=kind,
            quantity_delta=delta,
            reason="Teste concorrente ficticio.",
        )

    def assert_ledger(self, expected):
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, expected)
        self.assertEqual(
            StockMovement.objects.filter(product=self.product).aggregate(
                total=Sum("quantity_delta")
            )["total"],
            expected,
        )

    def test_two_adjustments_wait_and_accumulate_without_lost_update(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(lambda: self.adjust(-3)),
            lambda *_: self.outcome(lambda: self.adjust(5)),
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
        )
        self.assertEqual((first[0], second[0]), ("ok", "ok"))
        self.assert_ledger(12)

    def test_adjustment_first_purchase_waits_then_rejects_insufficient_stock(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(lambda: self.adjust(-10)),
            lambda *_: self.outcome(self.buy),
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "insufficient_stock"))
        self.assertFalse(Order.objects.exists())
        self.assert_ledger(0)

    def test_purchase_first_adjustment_rechecks_reserved_balance(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(lambda: self.buy(8)),
            lambda *_: self.outcome(lambda: self.adjust(-3)),
            pause_first_insert=True,
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "stock_limit_exceeded"))
        self.assert_ledger(2)

    def test_entry_first_waiting_purchase_can_use_committed_units(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(lambda: self.adjust(5, "ENTRY")),
            lambda *_: self.outcome(lambda: self.buy(12)),
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
        )
        self.assertEqual((first[0], second[0]), ("ok", "ok"))
        self.assert_ledger(3)

    def test_price_update_first_purchase_uses_new_committed_price(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(
                lambda: save_product(
                    user=self.admin, product_id=self.product.pk, data={"price": "30.00"}
                )
            ),
            lambda *_: self.outcome(lambda: self.buy(2)),
            pause_before=lambda sql: sql.startswith('UPDATE "catalog_product"'),
        )
        self.assertEqual((first[0], second[0]), ("ok", "ok"))
        order = Order.objects.get(pk=second[1])
        self.assertEqual(order.total, Decimal("60.00"))
        self.assertEqual(order.items.get().unit_price, Decimal("30.00"))
        self.assert_ledger(8)

    def test_purchase_first_price_update_preserves_old_snapshot(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(lambda: self.buy(2)),
            lambda *_: self.outcome(
                lambda: save_product(
                    user=self.admin, product_id=self.product.pk, data={"price": "30.00"}
                )
            ),
            pause_first_insert=True,
        )
        self.assertEqual((first[0], second[0]), ("ok", "ok"))
        self.assertEqual(Order.objects.get(pk=first[1]).total, Decimal("51.80"))
        self.assertEqual(Product.objects.get(pk=self.product.pk).price, Decimal("30.00"))
        self.assert_ledger(8)

    def test_deactivation_first_waiting_purchase_rejects_inactive(self):
        first, second = self.run_contended(
            lambda *_: self.outcome(
                lambda: save_product(
                    user=self.admin, product_id=self.product.pk, data={"is_active": False}
                )
            ),
            lambda *_: self.outcome(self.buy),
            pause_before=lambda sql: sql.startswith('UPDATE "catalog_product"'),
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "product_inactive"))
        self.assertFalse(Order.objects.exists())
        self.assert_ledger(10)

    def test_duplicate_sku_race_creates_only_one_product_and_stock(self):
        def create():
            return save_product(
                user=self.admin,
                data={"sku": "CONCURRENT-SKU", "name": "Produto Ficticio", "price": "1.00"},
            )

        first, second = self.run_contended(
            lambda *_: self.outcome(create),
            lambda *_: self.outcome(create),
            pause_before=lambda sql: sql.startswith('INSERT INTO "inventory_stock"'),
        )
        self.assertEqual(first[0], "ok")
        self.assertEqual(second, ("conflict", "sku_conflict"))
        self.assertEqual(Product.objects.filter(sku="CONCURRENT-SKU").count(), 1)
        self.assertEqual(Stock.objects.filter(product__sku="CONCURRENT-SKU").count(), 1)

    def test_adjustment_first_cancel_waits_and_restores_only_reserved_units(self):
        order = self.buy(3)
        first, second = self.run_contended(
            lambda *_: self.outcome(lambda: self.adjust(-2)),
            lambda *_: self.outcome(lambda: cancel_order(user=self.user, order_id=order.pk).order),
            pause_before=lambda sql: sql.startswith('UPDATE "inventory_stock"'),
        )
        self.assertEqual((first[0], second[0]), ("ok", "ok"))
        self.assert_ledger(8)
