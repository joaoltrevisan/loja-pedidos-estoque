import itertools
from datetime import timedelta
from decimal import Decimal
from functools import partial

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from accounts.models import Customer, User
from catalog.models import Product
from common.fields import StrictIntegerField
from inventory.models import Stock, StockMovement
from orders.models import Order, OrderItem, Shipment, SimulatedPayment


class StrictIntegerTests(SimpleTestCase):
    def test_rejects_fractional_boolean_and_nonfinite_input(self):
        field = StrictIntegerField()
        for value in (
            True,
            False,
            1.0,
            1.5,
            "1.5",
            "1e2",
            "",
            Decimal("1.5"),
            Decimal("NaN"),
            Decimal("Infinity"),
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                field.get_prep_value(value)

    def test_accepts_integral_values(self):
        field = StrictIntegerField()
        for value, expected in ((0, 0), (-3, -3), ("12", 12), (Decimal("2.0"), 2), (None, None)):
            with self.subTest(value=value):
                self.assertEqual(field.get_prep_value(value), expected)


class SchemaTests(TestCase):
    @classmethod
    def setUpClass(cls):
        if connection.vendor != "postgresql":
            raise RuntimeError("Estes testes exigem PostgreSQL real; SQLite nao e permitido.")
        super().setUpClass()

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="cliente@example.com", name="Cliente Ficticio", password="Portfolio-Ficticio-728!"
        )
        cls.customer = Customer.objects.create(user=cls.user)
        cls.product = Product.objects.create(
            sku="NOTEBOOK-A5", name="Caderno Horizonte", price=Decimal("25.90")
        )
        cls.stock = Stock.objects.create(product=cls.product, available_quantity=10)
        cls.order = cls.make_order()
        cls.item = OrderItem.objects.create(
            order=cls.order,
            product=cls.product,
            quantity=1,
            unit_price=Decimal("25.90"),
            product_sku=cls.product.sku,
            product_name=cls.product.name,
        )

    @classmethod
    def make_order(cls, **overrides):
        values = {
            "customer": cls.customer,
            "total": Decimal("25.90"),
            "shipping_recipient": "Cliente Ficticio",
            "shipping_street": "Rua Imaginaria",
            "shipping_number": "123",
            "shipping_district": "Bairro Modelo",
            "shipping_city": "Sao Paulo",
            "shipping_state": "SP",
            "shipping_postal_code": "01001000",
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def assert_constraint(self, name, operation):
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            operation()
            # FKs do Django sao deferidas: verificar dentro deste savepoint.
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        if name:
            self.assertEqual(caught.exception.__cause__.diag.constraint_name, name)

    def raw_update(self, record, field, value):
        # Identificadores vem dos modelos e sao escapados; valores sao parametrizados.
        quote = connection.ops.quote_name
        table = quote(record._meta.db_table)
        column = quote(record._meta.get_field(field).column)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET {column} = %s WHERE id = %s", [value, record.pk])

    def payment(self, **overrides):
        values = {"order": self.order, "amount": self.order.total, "approved_at": timezone.now()}
        values.update(overrides)
        return SimulatedPayment.objects.create(**values)

    def movement(self, **overrides):
        values = {
            "product": self.product,
            "performed_by": self.user,
            "movement_type": "ENTRY",
            "quantity_delta": 10,
            "reason": "Entrada ficticia de teste",
        }
        values.update(overrides)
        return StockMovement.objects.create(**values)

    def test_database_is_postgresql_and_role_is_not_superuser(self):
        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            self.assertFalse(cursor.fetchone()[0])

    def test_user_manager_normalizes_email_hashes_password_and_defaults_permissions(self):
        user = User.objects.create_user(
            "  OUTRO@EXAMPLE.COM  ", "Ficticio-927!", name="Outro Cliente"
        )
        self.assertEqual(user.email, "outro@example.com")
        self.assertNotEqual(user.password, "Ficticio-927!")
        self.assertTrue(user.check_password("Ficticio-927!"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(User.objects.get_by_natural_key("OUTRO@EXAMPLE.COM"), user)

    def test_empty_email_and_invalid_superuser_flags_are_rejected(self):
        for email in ("", " "):
            with self.subTest(email=email), self.assertRaises(ValueError):
                User.objects.create_user(email, name="Teste")
        for flags in ({"is_staff": False}, {"is_superuser": False}):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                User.objects.create_superuser("admin@example.com", name="Admin Ficticio", **flags)
        admin = User.objects.create_superuser(
            "admin@example.com", "Ficticio-927!", name="Admin Ficticio"
        )
        self.assertTrue(admin.is_staff and admin.is_superuser)

    def test_email_uniqueness_ignores_case_even_without_manager(self):
        self.assert_constraint(
            "user_email_ci_unique",
            lambda: User.objects.create(email="CLIENTE@EXAMPLE.COM", name="Duplicado"),
        )

    def test_required_user_fields_at_database_level(self):
        for updates, constraint in (
            ({"email": " "}, "user_email_not_blank_or_padded"),
            ({"email": " padded@example.com"}, "user_email_not_blank_or_padded"),
            ({"name": "\t "}, "user_name_required"),
        ):
            with self.subTest(updates=updates):
                self.assert_constraint(
                    constraint, partial(User.objects.filter(pk=self.user.pk).update, **updates)
                )

    def test_customer_and_stock_are_unique(self):
        self.assert_constraint(None, lambda: Customer.objects.create(user=self.user))
        self.assert_constraint(None, lambda: Stock.objects.create(product=self.product))

    def test_product_sku_name_and_uniqueness(self):
        self.assert_constraint(
            None, lambda: Product.objects.create(sku=self.product.sku, name="Outro", price="1.00")
        )
        for sku in ("", "abc", "WITH SPACE", "A\n"):
            with self.subTest(sku=sku):
                self.assert_constraint(
                    "product_sku_format",
                    partial(Product.objects.filter(pk=self.product.pk).update, sku=sku),
                )
        self.assert_constraint(
            "product_name_required",
            lambda: Product.objects.filter(pk=self.product.pk).update(name=" \t"),
        )

    def test_nonpositive_and_nan_money_rejected_by_database(self):
        payment = self.payment()
        for record, field, constraint in (
            (self.product, "price", "product_price_positive_finite"),
            (self.item, "unit_price", "item_price_positive_finite"),
            (self.order, "total", "order_total_positive_finite"),
            (payment, "amount", "payment_amount_positive_finite"),
        ):
            for value in (Decimal("0.00"), Decimal("-0.01"), Decimal("NaN")):
                with self.subTest(model=type(record).__name__, value=value):
                    self.assert_constraint(
                        constraint,
                        partial(self.raw_update, record, field, value),
                    )

    def test_money_precision_and_limits(self):
        self.product.full_clean()
        for price in (Decimal("1.001"), Decimal("100000000.00"), Decimal("Infinity")):
            product = Product(sku="PRECISION", name="Produto Ficticio", price=price)
            with self.subTest(price=price), self.assertRaises(ValidationError):
                product.full_clean()
        Product.objects.filter(pk=self.product.pk).update(price=Decimal("99999999.99"))
        Order.objects.filter(pk=self.order.pk).update(total=Decimal("99999999999999.99"))
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("99999999.99"))
        self.assertEqual(self.order.total, Decimal("99999999999999.99"))

    def test_stock_cannot_be_negative_but_zero_is_valid(self):
        self.assert_constraint(
            "stock_quantity_nonnegative",
            lambda: Stock.objects.filter(pk=self.stock.pk).update(available_quantity=-1),
        )
        Stock.objects.filter(pk=self.stock.pk).update(available_quantity=0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_quantity, 0)

    def test_item_quantity_bounds_and_duplicate_product(self):
        for quantity in (0, -1, 10000):
            with self.subTest(quantity=quantity):
                self.assert_constraint(
                    "item_quantity_valid",
                    partial(OrderItem.objects.filter(pk=self.item.pk).update, quantity=quantity),
                )
        self.assert_constraint(
            "item_order_product_unique",
            lambda: OrderItem.objects.create(
                order=self.order,
                product=self.product,
                quantity=1,
                unit_price="25.90",
                product_sku=self.product.sku,
                product_name=self.product.name,
            ),
        )
        OrderItem.objects.filter(pk=self.item.pk).update(quantity=9999)

    def test_fractional_and_boolean_values_are_not_truncated_by_orm(self):
        for record, field in ((self.stock, "available_quantity"), (self.item, "quantity")):
            for value in (True, False, 1.5, "1.5", Decimal("1.5")):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    type(record).objects.filter(pk=record.pk).update(**{field: value})
        with self.assertRaises(ValidationError):
            self.movement(quantity_delta=Decimal("1.5"))

    def test_historical_item_values_survive_catalog_changes(self):
        Product.objects.filter(pk=self.product.pk).update(
            price=Decimal("30.00"), sku="NEW-SKU", name="Nome novo", is_active=False
        )
        self.item.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.item.unit_price, Decimal("25.90"))
        self.assertEqual(self.item.product_sku, "NOTEBOOK-A5")
        self.assertEqual(self.item.product_name, "Caderno Horizonte")
        self.assertEqual(self.item.subtotal, Decimal("25.90"))
        self.assertEqual(self.order.total, Decimal("25.90"))

    def test_snapshot_fields_required(self):
        for field, value in (("product_name", "\t"), ("product_sku", "invalid sku")):
            with self.subTest(field=field):
                self.assert_constraint(
                    "item_snapshot_required",
                    partial(OrderItem.objects.filter(pk=self.item.pk).update, **{field: value}),
                )

    def test_address_and_currency_constraints(self):
        invalid = {
            "shipping_recipient": " ",
            "shipping_street": "",
            "shipping_number": " ",
            "shipping_district": "\t",
            "shipping_city": "",
            "shipping_state": "XX",
            "shipping_country": "US",
            "shipping_postal_code": "01001-00",
        }
        for field, value in invalid.items():
            with self.subTest(field=field):
                self.assert_constraint(
                    "order_shipping_address_valid",
                    partial(Order.objects.filter(pk=self.order.pk).update, **{field: value}),
                )
        self.assert_constraint(
            "order_currency_brl",
            lambda: Order.objects.filter(pk=self.order.pk).update(currency="USD"),
        )

    def test_every_status_and_timestamp_presence_combination(self):
        fields = ("paid_at", "cancelled_at", "shipped_at", "delivered_at")
        allowed = {
            "PENDING_PAYMENT": (False, False, False, False),
            "CANCELLED": (False, True, False, False),
            "PAID": (True, False, False, False),
            "SHIPPED": (True, False, True, False),
            "DELIVERED": (True, False, True, True),
        }
        at = self.order.created_at + timedelta(seconds=1)
        for status in (*allowed, "INVALID"):
            for flags in itertools.product((False, True), repeat=4):
                values = {
                    field: at if flag else None for field, flag in zip(fields, flags, strict=True)
                }
                values["status"] = status
                with self.subTest(status=status, timestamps=flags):
                    update = partial(Order.objects.filter(pk=self.order.pk).update, **values)
                    if allowed.get(status) == flags:
                        update()
                    else:
                        self.assert_constraint("order_status_timestamps_valid", update)

    def test_order_chronology_rejects_events_out_of_order(self):
        at = self.order.created_at
        cases = [
            {"status": "PAID", "paid_at": at - timedelta(seconds=1)},
            {"status": "CANCELLED", "cancelled_at": at - timedelta(seconds=1)},
            {"status": "SHIPPED", "paid_at": at + timedelta(seconds=2), "shipped_at": at},
            {
                "status": "DELIVERED",
                "paid_at": at,
                "shipped_at": at + timedelta(seconds=2),
                "delivered_at": at,
            },
        ]
        for values in cases:
            with self.subTest(values=values):
                self.assert_constraint(
                    "order_timestamps_chronological",
                    partial(Order.objects.filter(pk=self.order.pk).update, **values),
                )

    def test_payment_one_per_order_reference_unique_and_simulation_mandatory(self):
        first = self.payment()
        self.assertTrue(first.is_simulated)
        self.assertIn("NO REAL CHARGE", str(first))
        self.assert_constraint(None, self.payment)
        another = self.make_order()
        self.assert_constraint(None, lambda: self.payment(order=another, reference=first.reference))
        self.assert_constraint(
            "payment_simulation_required",
            lambda: SimulatedPayment.objects.filter(pk=first.pk).update(is_simulated=False),
        )

    def test_shipment_unique_and_delivery_not_before_shipping(self):
        at = timezone.now()
        shipment = Shipment.objects.create(order=self.order, shipped_at=at)
        self.assert_constraint(
            None, lambda: Shipment.objects.create(order=self.order, shipped_at=at)
        )
        self.assert_constraint(
            "shipment_dates_chronological",
            lambda: Shipment.objects.filter(pk=shipment.pk).update(
                delivered_at=at - timedelta(seconds=1)
            ),
        )
        Shipment.objects.filter(pk=shipment.pk).update(delivered_at=at)

    def test_movement_sign_type_and_order_combinations(self):
        allowed = {
            ("ENTRY", 1, False),
            ("ADJUSTMENT", 1, False),
            ("ADJUSTMENT", -1, False),
            ("RESERVATION", -1, True),
            ("RELEASE", 1, True),
        }
        for kind, delta, has_order in itertools.product(
            ("ENTRY", "ADJUSTMENT", "RESERVATION", "RELEASE", "INVALID"), (-1, 0, 1), (False, True)
        ):
            kwargs = {
                "movement_type": kind,
                "quantity_delta": delta,
                "order": self.order if has_order else None,
            }
            with self.subTest(**kwargs):
                if (kind, delta, has_order) in allowed:
                    self.movement(**kwargs)
                else:
                    self.assert_constraint(
                        "movement_type_sign_order_valid", partial(self.movement, **kwargs)
                    )

    def test_duplicate_reservation_and_release_rejected_but_entries_can_repeat(self):
        for kind, delta in (("RESERVATION", -1), ("RELEASE", 1)):
            self.movement(movement_type=kind, quantity_delta=delta, order=self.order)
            self.assert_constraint(
                "movement_order_product_type_unique",
                partial(self.movement, movement_type=kind, quantity_delta=delta, order=self.order),
            )
        self.movement()
        self.movement()

    def test_movement_reason_and_symmetric_range(self):
        self.assert_constraint("movement_reason_required", lambda: self.movement(reason=" \t"))
        self.assert_constraint(
            "movement_delta_symmetric_range",
            lambda: self.movement(movement_type="ADJUSTMENT", quantity_delta=-2147483648),
        )

    def test_orm_protects_historical_relationships(self):
        self.payment()
        Shipment.objects.create(order=self.order, shipped_at=timezone.now())
        self.movement(order=self.order, movement_type="RESERVATION", quantity_delta=-1)
        for record in (self.user, self.customer, self.product, self.order):
            with self.subTest(record=type(record).__name__), self.assertRaises(ProtectedError):
                record.delete()
        for model in (Customer, Stock, Order, OrderItem, SimulatedPayment, Shipment, StockMovement):
            for field in model._meta.fields:
                if isinstance(field, models.ForeignKey):
                    self.assertIs(field.remote_field.on_delete, models.PROTECT)

    def test_foreign_keys_protect_against_raw_sql_and_orphans(self):
        def delete_product():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM catalog_product WHERE id = %s", [self.product.pk])

        self.assert_constraint(None, delete_product)
        self.assert_constraint(
            None, lambda: OrderItem.objects.filter(pk=self.item.pk).update(product_id=999999999)
        )

    def test_dates_are_timezone_aware(self):
        self.assertTrue(timezone.is_aware(self.order.created_at))
        payment = self.payment()
        payment.refresh_from_db()
        self.assertTrue(timezone.is_aware(payment.approved_at))
        self.assertEqual(payment.approved_at.utcoffset(), timedelta(0))
