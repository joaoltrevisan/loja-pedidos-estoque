import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event

from django.db import close_old_connections, connection, connections


class ControlledConcurrencyMixin:
    def run_contended(
        self,
        first_operation,
        second_operation,
        *,
        pause_first_insert=False,
        pause_before=None,
        expect_stock_select=False,
    ):
        """Observa bloqueio REAL no PG antes de liberar a primeira transacao."""
        locked, release = Event(), Event()
        pids = Queue()

        def worker(label, operation):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '10s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put((label, cursor.fetchone()[0]))

                def pause(execute, sql, params, many, context):
                    if label == "first" and (
                        (pause_first_insert and sql.startswith('INSERT INTO "orders_order"'))
                        or (pause_before is not None and pause_before(sql))
                    ):
                        # Ponto controlado pelo teste, com bloqueio ja adquirido.
                        locked.set()
                        if not release.wait(5):
                            raise TimeoutError("Teste nao liberou a primeira compra")
                    return execute(sql, params, many, context)

                with connection.execute_wrapper(pause):
                    return operation(locked, release)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                first = pool.submit(worker, "first", first_operation)
                label, first_pid = pids.get(timeout=5)
                self.assertEqual(label, "first")
                self.assertTrue(locked.wait(3), "Primeira operacao nao alcancou o ponto controlado")
                second = pool.submit(worker, "second", second_operation)
                label, second_pid = pids.get(timeout=5)
                self.assertEqual(label, "second")
                self.assertNotEqual(first_pid, second_pid)
                deadline = time.monotonic() + 3
                blocked = False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [second_pid])
                        blocked = first_pid in cursor.fetchone()[0]
                    if blocked or second.done():
                        break
                    time.sleep(0.01)
                self.assertTrue(blocked, "Segunda conexao nao aguardou o bloqueio da primeira")
                self.assertFalse(second.done())
                if expect_stock_select:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT query FROM pg_stat_activity WHERE pid = %s", [second_pid]
                        )
                        waiting_query = cursor.fetchone()[0]
                    self.assertTrue(waiting_query.startswith("SELECT"))
                    self.assertIn('"inventory_stock"', waiting_query)
                    self.assertIn("FOR UPDATE", waiting_query)
            finally:
                release.set()
            return first.result(timeout=10), second.result(timeout=10)
