from concurrent.futures import ThreadPoolExecutor
from datetime import date
from queue import Queue
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from orders.lifecycle import approve_simulated_payment
from orders.services import create_order
from reports.selectors import revenue_report
from tests.order_fixtures import ADDRESS, build_order_fixtures
from tests.report_fixtures import instant


class ReportConcurrencyTests(TransactionTestCase):
    def run_payment_race(self, *, commit_after_aggregate=False):
        locked, release = Event(), Event()
        writer_pid = Queue()
        with patch("django.utils.timezone.now", return_value=instant("2026-01-01T10:00:00")):
            build_order_fixtures(self)
            order = create_order(
                user=self.user,
                items=[{"product_id": self.product.pk, "quantity": 1}],
                shipping_address=ADDRESS,
            )

            def pay():
                close_old_connections()
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SET statement_timeout = '8s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        writer_pid.put(cursor.fetchone()[0])

                    def pause(execute, sql, params, many, context):
                        if sql.startswith('UPDATE "orders_order"'):
                            # Pagamento ja inserido, mas a transacao ainda nao confirmou.
                            locked.set()
                            if not release.wait(5):
                                raise TimeoutError("Pagamento de teste nao foi liberado.")
                        return execute(sql, params, many, context)

                    with connection.execute_wrapper(pause):
                        approve_simulated_payment(user=self.admin, order_id=order.pk)
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(pay)
                try:
                    self.assertTrue(locked.wait(3))
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        self.assertNotEqual(cursor.fetchone()[0], writer_pid.get(timeout=1))
                        cursor.execute("SET statement_timeout = '3s'")

                    def commit_between_execute_and_fetch(execute, sql, params, many, context):
                        result = execute(sql, params, many, context)
                        if 'FROM "orders_simulatedpayment"' in sql and "GROUP BY" in sql:
                            release.set()
                            future.result(timeout=5)
                        return result

                    kwargs = {
                        "user": self.admin,
                        "start": date(2026, 1, 1),
                        "end": date(2026, 1, 2),
                    }
                    if commit_after_aggregate:
                        with connection.execute_wrapper(commit_between_execute_and_fetch):
                            before = revenue_report(**kwargs)
                    else:
                        before = revenue_report(**kwargs)
                        self.assertFalse(future.done())
                    self.assertEqual((before["total"], before["paid_orders"]), (0, 0))
                    self.assertEqual(before["series"][0]["amount"], 0)
                finally:
                    release.set()
                    with connection.cursor() as cursor:
                        cursor.execute("SET statement_timeout = '0'")
                future.result(timeout=5)
            after = revenue_report(**kwargs)
            self.assertEqual(str(after["total"]), "25.90")
            self.assertEqual(after["paid_orders"], 1)
            self.assertEqual(after["series"][0]["amount"], after["total"])

    def test_report_does_not_read_uncommitted_simulated_payment(self):
        self.run_payment_race()

    def test_total_and_series_share_snapshot_when_payment_commits_mid_response(self):
        self.run_payment_race(commit_after_aggregate=True)
