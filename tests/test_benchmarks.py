import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.db import connection, transaction
from django.db.models import Count
from django.test import SimpleTestCase, TestCase

from accounts.models import User
from benchmarks.audit import audit_dataset
from benchmarks.dataset import DOMAIN, create_dataset, require_isolated_database, validate_sizes
from benchmarks.runner import (
    domain_fingerprint,
    explain,
    fingerprint,
    measure_n_plus_one,
    measure_phase,
)
from catalog.models import Product
from inventory.models import Stock, StockMovement
from orders.integrity import inspect_order_history
from orders.models import Order, SimulatedPayment
from scripts.benchmark_stage9 import main, write_result


class BenchmarkSafetyTests(SimpleTestCase):
    def test_final_write_preserves_evidence_when_two_parent_checks_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result.json"
            # As duas execucoes veem o caminho livre antes de gerar suas cargas.
            self.assertFalse(output.exists())
            self.assertFalse(output.exists())
            write_result(output, {"run": "first"})
            with self.assertRaises(FileExistsError):
                write_result(output, {"run": "second"})
            self.assertEqual(output.read_text(), '{\n  "run": "first"\n}\n')

    def test_sizes_reject_booleans_unbounded_volumes_and_invalid_seed(self):
        for values in (
            (True, 2, 10, 42),
            (0, 2, 10, 42),
            (100001, 2, 10, 42),
            (1, 1, 10, 42),
            (1, 2001, 10, 42),
            (1, 2, 9, 42),
            (1, 2, 5001, 42),
            (1, 2, 10, -1),
            (1, 2, 10, True),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_sizes(*values)

    def test_explain_rejects_mutations_before_opening_a_cursor(self):
        for query in ("DELETE FROM orders_order", "UPDATE orders_order SET total=1", "VACUUM"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                explain(query, ())

    def test_measurement_records_real_samples_and_excludes_warmups(self):
        plans = [{"Execution Time": float(i)} for i in (100, 100, 1, 3, 2)]
        with patch("benchmarks.runner.explain", side_effect=plans) as probe:
            result = measure_phase({"sample": ("SELECT 1", ())}, 3, 42)
        self.assertEqual(probe.call_count, 5)
        self.assertEqual(result["sample"]["execution_ms"], {"min": 1.0, "median": 2.0, "max": 3.0})
        self.assertEqual(result["sample"]["samples"], plans[2:])

    def test_created_database_is_removed_even_if_child_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            output = str(Path(folder) / "result.json")
            controller = MagicMock()
            manager = MagicMock()
            manager.__enter__.return_value = controller
            with (
                patch("sys.argv", ["benchmark_stage9.py", "--output", output]),
                patch("scripts.benchmark_stage9.psycopg.connect", return_value=manager),
                patch(
                    "scripts.benchmark_stage9.subprocess.run",
                    side_effect=RuntimeError("child failed"),
                ),
                patch("django.db.connections.close_all"),
                self.assertRaisesRegex(RuntimeError, "child failed"),
            ):
                main()
            statements = [call.args[0].as_string() for call in controller.execute.call_args_list]
            self.assertEqual(len(statements), 2)
            self.assertTrue(statements[0].startswith('CREATE DATABASE "loja_bench_'))
            self.assertEqual(
                statements[1], statements[0].replace("CREATE DATABASE", "DROP DATABASE")
            )
            self.assertNotIn("FORCE", statements[1])

    def test_existing_output_is_preserved_before_database_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result.json"
            output.write_text("evidencia anterior")
            with (
                patch("sys.argv", ["benchmark_stage9.py", "--output", str(output)]),
                patch("scripts.benchmark_stage9.psycopg.connect") as connect,
                self.assertRaises(SystemExit),
            ):
                main()
            connect.assert_not_called()
            self.assertEqual(output.read_text(), "evidencia anterior")


class BenchmarkGeneratorTests(TestCase):
    def test_guard_refuses_normal_and_mismatched_database_without_writing(self):
        for expected in ("loja", "", "loja_bench_other"):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                create_dataset(expected_name=expected, orders=1, customers=2, products=10)
        self.assertFalse(User.objects.exists())

    def test_guard_accepts_only_matching_prefixed_database(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("loja_bench_owned",)
        manager = MagicMock()
        manager.__enter__.return_value = cursor
        with patch("benchmarks.dataset.connection.cursor", return_value=manager):
            require_isolated_database("loja_bench_owned")
            with self.assertRaises(ValueError):
                require_isolated_database("loja_bench_other")

    def test_failure_rolls_back_entire_dataset(self):
        # Apenas os testes usam seu banco descartavel no lugar do prefixo do runner.
        with (
            patch("benchmarks.dataset.require_isolated_database"),
            patch("benchmarks.dataset.create_order", side_effect=RuntimeError("failure")),
            self.assertRaisesRegex(RuntimeError, "failure"),
        ):
            create_dataset(expected_name="test_only", orders=1, customers=2, products=10)
        for model in DOMAIN:
            self.assertFalse(model.objects.exists(), model._meta.label)

    def test_repetition_refuses_nonempty_domain_without_overwriting(self):
        user = User.objects.create_user("existing@example.com", name="Ficticio")
        with (
            patch("benchmarks.dataset.require_isolated_database"),
            self.assertRaisesRegex(ValueError, "vazia"),
        ):
            create_dataset(expected_name="test_only", orders=1, customers=2, products=10)
        self.assertEqual(list(User.objects.values_list("pk", flat=True)), [user.pk])

    def test_same_seed_reproduces_business_values_independent_of_sequences(self):
        results = []
        for _ in range(2):
            with transaction.atomic():
                with patch("benchmarks.dataset.require_isolated_database"):
                    create_dataset(expected_name="test_only", orders=10, customers=3, products=10)
                values = [
                    {
                        "customer": order.customer.user.email,
                        "status": order.status,
                        "total": order.total,
                        "created_at": order.created_at,
                        "paid_at": order.paid_at,
                        "items": list(
                            order.items.order_by("product_sku").values_list(
                                "product_sku", "quantity", "unit_price"
                            )
                        ),
                    }
                    for order in Order.objects.select_related("customer__user").order_by("id")
                ]
                results.append(fingerprint(values))
                transaction.set_rollback(True)
        self.assertEqual(results[0], results[1])


class BenchmarkDatasetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with patch("benchmarks.dataset.require_isolated_database"):
            cls.admin = create_dataset(
                expected_name="test_only", orders=100, customers=10, products=20
            )

    def test_all_states_and_histories_are_coherent(self):
        audit = audit_dataset()
        self.assertFalse(any(audit["violations"].values()))
        self.assertEqual(
            dict(Order.objects.values_list("status").annotate(count=Count("id"))),
            {"PENDING_PAYMENT": 5, "PAID": 30, "SHIPPED": 25, "DELIVERED": 35, "CANCELLED": 5},
        )
        for order in Order.objects.select_related("customer").all():
            inspect_order_history(order)

    def test_accounts_have_unusable_passwords_and_fictitious_emails(self):
        self.assertEqual(User.objects.count(), 11)
        self.assertTrue(
            all(
                not user.has_usable_password() and user.email.endswith("@example.com")
                for user in User.objects.all()
            )
        )
        self.assertFalse(SimulatedPayment.objects.filter(is_simulated=False).exists())

    def test_historical_items_survive_catalog_change(self):
        product = Product.objects.order_by("id").first()
        self.assertFalse(product.is_active)
        self.assertTrue(product.order_items.exists())
        self.assertTrue(
            all(item.unit_price == product.price - 5 for item in product.order_items.all())
        )

    def test_audit_detects_stock_corruption(self):
        stock = Stock.objects.first()
        Stock.objects.filter(pk=stock.pk).update(available_quantity=stock.available_quantity + 1)
        with self.assertRaisesRegex(ValueError, "stock_ledger"):
            audit_dataset()

    def test_audit_detects_payment_corruption(self):
        payment = SimulatedPayment.objects.first()
        SimulatedPayment.objects.filter(pk=payment.pk).update(amount=payment.amount + 1)
        with self.assertRaisesRegex(ValueError, "payments"):
            audit_dataset()

    def test_audit_detects_reservation_actor_corruption(self):
        movement = StockMovement.objects.filter(movement_type="RESERVATION").first()
        StockMovement.objects.filter(pk=movement.pk).update(performed_by=self.admin)
        with self.assertRaisesRegex(ValueError, "reservations"):
            audit_dataset()

    def test_prefetch_and_http_query_counts_stay_constant_at_maximum_page_size(self):
        before = domain_fingerprint()
        rows = measure_n_plus_one(self.admin)
        self.assertEqual([row["naive_queries"] for row in rows], [4, 61, 301])
        self.assertEqual([row["optimized_queries"] for row in rows], [2, 2, 2])
        self.assertEqual([row["api_queries"] for row in rows], [4, 4, 4])
        self.assertTrue(all(row["payloads_equal"] for row in rows))
        self.assertEqual(domain_fingerprint(), before)

    def test_domain_fingerprint_detects_changes_outside_counting_audit(self):
        before = domain_fingerprint()
        product = Product.objects.first()
        Product.objects.filter(pk=product.pk).update(description="Outra descricao ficticia")
        self.assertNotEqual(domain_fingerprint(), before)
        self.assertFalse(any(audit_dataset()["violations"].values()))

    def test_postgresql_explain_contains_execution_and_buffers(self):
        sql, params = Order.objects.filter(pk=Order.objects.first().pk).query.sql_with_params()
        plan = explain(sql, params)
        self.assertIn("Execution Time", plan)
        self.assertIn("Shared Hit Blocks", plan["Plan"])
        self.assertEqual(plan["Plan"]["Actual Rows"], 1)
        self.assertEqual(connection.vendor, "postgresql")
