import io
import os
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Sum
from django.test import TestCase, override_settings

from accounts.models import Customer, User
from catalog.models import Product
from inventory.models import Stock, StockMovement
from orders import demo_data
from orders.models import Order, OrderItem, Shipment, SimulatedPayment
from orders.validation import ADDRESS_FIELDS


@override_settings(ENABLE_DEMO_DATA=True)
class DemoDataTests(TestCase):
    def setUp(self):
        self.password_env = patch.dict(os.environ, {"DEMO_PASSWORD": "Ficticio-Demonstracao-2026!"})
        self.password_env.start()
        self.addCleanup(self.password_env.stop)

    def seed(self):
        output = io.StringIO()
        call_command("seed_demo", stdout=output)
        self.assertIn("PAGAMENTOS SIMULADOS", output.getvalue())
        self.assertNotIn(os.environ["DEMO_PASSWORD"], output.getvalue())

    def assert_empty_domain(self):
        for model in (
            User,
            Customer,
            Product,
            Stock,
            Order,
            OrderItem,
            SimulatedPayment,
            Shipment,
            StockMovement,
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)

    def test_known_counts_totals_and_balances(self):
        self.seed()
        for model, expected in (
            (User, 4),
            (Customer, 3),
            (Product, 3),
            (Stock, 3),
            (Order, 5),
            (OrderItem, 7),
            (SimulatedPayment, 3),
            (Shipment, 2),
            (StockMovement, 11),
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), expected)
        self.assertEqual(
            dict(Order.objects.values_list("status", "total")),
            {
                "PENDING_PAYMENT": Decimal("77.70"),
                "PAID": Decimal("79.80"),
                "SHIPPED": Decimal("34.90"),
                "DELIVERED": Decimal("53.40"),
                "CANCELLED": Decimal("51.80"),
            },
        )
        self.assertEqual(
            dict(Stock.objects.values_list("product__sku", "available_quantity")),
            {"DEMO-CADERNO": 26, "DEMO-CANECA": 17, "DEMO-CANETA": 45},
        )
        self.assertEqual(
            SimulatedPayment.objects.aggregate(value=Sum("amount"))["value"], Decimal("168.10")
        )

    def test_order_payment_shipment_and_ledger_are_consistent(self):
        self.seed()
        paid_statuses = (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)
        for order in Order.objects.all():
            with self.subTest(status=order.status):
                self.assertEqual(
                    order.total, sum((item.subtotal for item in order.items.all()), Decimal("0.00"))
                )
                payment = SimulatedPayment.objects.filter(order=order).first()
                self.assertEqual(payment is not None, order.status in paid_statuses)
                if payment:
                    self.assertEqual(payment.amount, order.total)
                    self.assertEqual(payment.approved_at, order.paid_at)
                    self.assertTrue(payment.is_simulated)
                shipment = Shipment.objects.filter(order=order).first()
                self.assertEqual(
                    shipment is not None,
                    order.status in (Order.Status.SHIPPED, Order.Status.DELIVERED),
                )
                if shipment:
                    self.assertEqual(shipment.shipped_at, order.shipped_at)
                    self.assertEqual(shipment.delivered_at, order.delivered_at)
                    self.assertTrue(shipment.tracking_code.startswith("SIMULATED-"))
                for item in order.items.all():
                    reserve = order.stock_movements.get(
                        product=item.product, movement_type="RESERVATION"
                    )
                    self.assertEqual(reserve.quantity_delta, -item.quantity)
                    self.assertEqual(reserve.performed_by_id, order.customer.user_id)
                    releases = order.stock_movements.filter(
                        product=item.product, movement_type="RELEASE"
                    )
                    self.assertEqual(releases.count(), int(order.status == Order.Status.CANCELLED))
                    if releases.exists():
                        self.assertEqual(releases.get().quantity_delta, item.quantity)
        for stock in Stock.objects.all():
            self.assertEqual(
                stock.available_quantity,
                stock.product.movements.aggregate(value=Sum("quantity_delta"))["value"],
            )

    def test_seed_never_erases_or_duplicates_existing_data(self):
        self.seed()
        before = list(Order.objects.values_list("pk", "total", "status"))
        with self.assertRaisesMessage(CommandError, "base de dominio vazia"):
            self.seed()
        self.assertEqual(list(Order.objects.values_list("pk", "total", "status")), before)
        self.assertEqual(User.objects.count(), 4)

    @override_settings(ENABLE_DEMO_DATA=False)
    def test_seed_requires_explicit_enable(self):
        with self.assertRaisesMessage(CommandError, "desabilitada"):
            self.seed()
        self.assert_empty_domain()

    def test_seed_requires_password_without_modifying_data(self):
        for password in ("", "curta"):
            with (
                self.subTest(password=password),
                patch.dict(os.environ, {"DEMO_PASSWORD": password}),
            ):
                with self.assertRaisesMessage(CommandError, "16 caracteres"):
                    self.seed()
        self.assert_empty_domain()

    def test_failure_after_stock_change_rolls_back_entire_dataset(self):
        original = demo_data.record_movement
        calls = 0

        def fail_on_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Falha controlada depois da primeira entrada de estoque")
            return original(*args, **kwargs)

        with patch("orders.demo_data.record_movement", side_effect=fail_on_second):
            with self.assertRaisesMessage(RuntimeError, "Falha controlada"):
                self.seed()
        self.assert_empty_domain()

    def test_order_service_failure_rolls_back_the_entire_dataset(self):
        original = demo_data.create_order
        calls = 0

        def fail_on_third(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("Falha controlada depois de dois pedidos")
            return original(**kwargs)

        with patch("orders.demo_data.create_order", side_effect=fail_on_third):
            with self.assertRaisesMessage(RuntimeError, "Falha controlada"):
                self.seed()
        self.assertEqual(calls, 3)
        self.assert_empty_domain()

    def test_lifecycle_failure_rolls_back_the_entire_dataset(self):
        with patch(
            "orders.demo_data.ship_order", side_effect=RuntimeError("Falha controlada no envio")
        ):
            with self.assertRaisesMessage(RuntimeError, "Falha controlada no envio"):
                self.seed()
        self.assert_empty_domain()

    def snapshot(self):
        return {
            "users": list(
                User.objects.order_by("email").values_list(
                    "email", "name", "date_joined", "is_staff"
                )
            ),
            "products": list(
                Product.objects.order_by("sku").values_list("sku", "price", "created_at")
            ),
            "orders": list(
                Order.objects.order_by("status").values_list(
                    "status",
                    "total",
                    "customer__user__email",
                    "created_at",
                    "paid_at",
                    "shipped_at",
                    "delivered_at",
                    "cancelled_at",
                    *[f"shipping_{field}" for field in (*ADDRESS_FIELDS, "country")],
                )
            ),
            "payments": list(
                SimulatedPayment.objects.order_by("reference").values_list(
                    "reference", "amount", "approved_at", "is_simulated"
                )
            ),
            "stocks": list(
                Stock.objects.order_by("product__sku").values_list(
                    "product__sku", "available_quantity", "updated_at"
                )
            ),
            "items": list(
                OrderItem.objects.order_by("order__status", "product_sku").values_list(
                    "order__status", "product_sku", "product_name", "quantity", "unit_price"
                )
            ),
            "shipments": list(
                Shipment.objects.order_by("order__status").values_list(
                    "order__status", "tracking_code", "shipped_at", "delivered_at"
                )
            ),
            "movements": list(
                StockMovement.objects.order_by(
                    "product__sku", "movement_type", "order__status"
                ).values_list(
                    "product__sku",
                    "movement_type",
                    "order__status",
                    "quantity_delta",
                    "performed_by__email",
                    "created_at",
                    "reason",
                )
            ),
        }

    def test_dataset_is_reproducible_in_empty_databases(self):
        with transaction.atomic():
            self.seed()
            first = self.snapshot()
            transaction.set_rollback(True)
        self.assert_empty_domain()
        self.seed()
        self.assertEqual(self.snapshot(), first)

    def test_credentials_are_hashed_and_only_admin_has_privileges(self):
        self.seed()
        for user in User.objects.all():
            with self.subTest(user=user.email):
                self.assertTrue(user.email.endswith(".demo@example.com"))
                self.assertTrue(user.check_password(os.environ["DEMO_PASSWORD"]))
                self.assertNotEqual(user.password, os.environ["DEMO_PASSWORD"])
                self.assertEqual(user.is_staff, user.email == "admin.demo@example.com")
                self.assertEqual(user.is_superuser, user.email == "admin.demo@example.com")
