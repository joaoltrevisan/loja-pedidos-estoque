"""Medicoes quentes: planos completos, resultados iguais e controles sem ganho."""

import hashlib
import json
import platform
import random
import statistics
import time
from datetime import UTC, date, datetime

import django
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from orders.models import Order
from orders.serializers import OrderDetailSerializer
from orders.views import readable_orders
from reports.periods import ReportPeriod
from reports.selectors import daily_revenue, low_stock, top_products

from .audit import audit_dataset
from .dataset import DOMAIN, create_dataset, require_isolated_database

INDEXES = {
    "payment_approved_at_idx": (
        "CREATE INDEX payment_approved_at_idx ON orders_simulatedpayment (approved_at)"
    ),
    "order_pending_created_idx": (
        "CREATE INDEX order_pending_created_idx ON orders_order (created_at, id) "
        "WHERE status='PENDING_PAYMENT'"
    ),
}


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, default=str, ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def domain_fingerprint():
    digest = hashlib.sha256()
    for model in DOMAIN:
        digest.update(model._meta.label.encode())
        for row in model.objects.order_by("pk").values().iterator(chunk_size=1000):
            digest.update(json.dumps(row, sort_keys=True, default=str).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def queries(admin):
    narrow = ReportPeriod(date(2025, 10, 15), date(2025, 10, 16))
    wide = ReportPeriod(date(2025, 1, 1), date(2026, 1, 1))
    first = Order.objects.order_by("id").first()
    # Mesmo filtro de oldest_pending, com relogio fixo para a comparacao.
    return {
        "oldest_pending": Order.objects.filter(
            status="PENDING_PAYMENT", created_at__lte=datetime(2026, 1, 3, tzinfo=UTC)
        ).order_by("created_at", "id")[:20],
        "revenue_day": daily_revenue(narrow),
        "revenue_year": daily_revenue(wide),
        "top_products_day": top_products(user=admin, start=narrow.start, end=narrow.end).order_by(
            "-units_sold", "product_id"
        )[:20],
        "customer_orders": Order.objects.filter(customer_id=first.customer_id).order_by(
            "-created_at", "id"
        )[:20],
        "primary_key": Order.objects.filter(pk=first.pk),
        "low_stock": low_stock(user=admin, threshold=25).order_by("available_quantity", "id")[:20],
    }


def inventory_indexes():
    with connection.cursor() as cursor:
        cursor.execute("""SELECT tablename,indexname,indexdef,pg_relation_size(indexname::regclass)
            FROM pg_indexes WHERE schemaname='public' AND
            (tablename LIKE 'orders_%%' OR tablename LIKE 'inventory_%%'
             OR tablename LIKE 'catalog_%%')
            ORDER BY tablename,indexname""")
        return [
            dict(zip(("table", "name", "definition", "bytes"), row, strict=True))
            for row in cursor.fetchall()
        ]


def explain(sql, params):
    # Somente SQL compilado das consultas SELECT fixas acima, sem entrada HTTP.
    if not sql.lstrip().upper().startswith("SELECT "):
        raise ValueError("Somente SELECT pode ser medido.")
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
        document = cursor.fetchone()[0]
    return (json.loads(document) if isinstance(document, str) else document)[0]


def measure_phase(compiled, repeats, seed):
    for sql, params in compiled.values():
        for _ in range(2):
            explain(sql, params)
    samples = {name: [] for name in compiled}
    rng = random.Random(seed)
    for _ in range(repeats):
        names = list(compiled)
        rng.shuffle(names)
        for name in names:
            samples[name].append(explain(*compiled[name]))
    return {
        name: {
            "execution_ms": {
                "min": min(times),
                "median": statistics.median(times),
                "max": max(times),
            },
            "samples": plans,
        }
        for name, plans in samples.items()
        for times in [[plan["Execution Time"] for plan in plans]]
    }


def measure_n_plus_one(admin, sizes=(1, 20, 100)):
    results = []
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(admin)}")
    for size in sizes:
        with CaptureQueriesContext(connection) as naive:
            plain = OrderDetailSerializer(Order.objects.order_by("id")[:size], many=True).data
        with CaptureQueriesContext(connection) as optimized:
            loaded = OrderDetailSerializer(
                readable_orders(admin).order_by("id")[:size], many=True
            ).data
        if plain != loaded:
            raise ValueError("O carregamento otimizado alterou o resultado.")
        cache.clear()
        with CaptureQueriesContext(connection) as api:
            response = client.get("/api/orders/", {"page_size": size}, HTTP_HOST="localhost")
        if response.status_code != 200 or len(response.data["results"]) != min(
            size, Order.objects.count()
        ):
            raise ValueError("A listagem HTTP nao retornou a pagina esperada.")
        results.append(
            {
                "page_size": size,
                "returned": len(loaded),
                "naive_queries": len(naive),
                "optimized_queries": len(optimized),
                "api_queries": len(api),
                "payload_sha256": fingerprint(loaded),
                "payloads_equal": True,
            }
        )
    return results


def run_benchmark(*, database, orders, customers, products, seed, repeats):
    require_isolated_database(database)
    if type(repeats) is not int or not 3 <= repeats <= 30:
        raise ValueError("Use de 3 a 30 repeticoes.")
    admin = create_dataset(
        expected_name=database,
        orders=orders,
        customers=customers,
        products=products,
        seed=seed,
        progress=lambda value: print(value, flush=True),
    )
    audit = audit_dataset()
    domain_before = domain_fingerprint()
    querysets = queries(admin)
    compiled = {name: queryset.query.sql_with_params() for name, queryset in querysets.items()}
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        settings = {}
        for name in (
            "shared_buffers",
            "work_mem",
            "effective_cache_size",
            "random_page_cost",
            "max_parallel_workers_per_gather",
            "jit",
            "enable_seqscan",
        ):
            cursor.execute("SELECT current_setting(%s)", [name])
            settings[name] = cursor.fetchone()[0]
        cursor.execute("VACUUM (ANALYZE)")
        # A migration final pode conter os candidatos. Retiro apenas estes indices
        # nao unicos, neste banco recem-criado, para reproduzir a base anterior.
        for name in INDEXES:
            cursor.execute(f'DROP INDEX IF EXISTS "{name}"')
    before_indexes = inventory_indexes()
    result_hashes = {}

    def hash_results():
        hashes = {}
        for name, (sql, params) in compiled.items():
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                hashes[name] = fingerprint(cursor.fetchall())
        return hashes

    result_hashes = hash_results()
    phases, builds = {}, []
    for phase, desired in (
        ("baseline", ()),
        ("payment_only", ("payment_approved_at_idx",)),
        ("both", tuple(INDEXES)),
        ("pending_only", ("order_pending_created_idx",)),
        ("baseline_again", ()),
    ):
        with connection.cursor() as cursor:
            for name in INDEXES:
                cursor.execute("SELECT to_regclass(%s)", [name])
                exists = cursor.fetchone()[0] is not None
                if exists and name not in desired:
                    cursor.execute(f'DROP INDEX "{name}"')
                if not exists and name in desired:
                    started = time.perf_counter()
                    cursor.execute(INDEXES[name])
                    elapsed = (time.perf_counter() - started) * 1000
                    cursor.execute("SELECT pg_relation_size(%s::regclass)", [name])
                    builds.append(
                        {
                            "phase": phase,
                            "index": name,
                            "build_ms": elapsed,
                            "bytes": cursor.fetchone()[0],
                        }
                    )
        print(f"Medindo fase {phase}", flush=True)
        phases[phase] = measure_phase(compiled, repeats, seed)
        if hash_results() != result_hashes:
            raise ValueError("Resultados SQL mudaram entre fases.")
    n_plus_one = measure_n_plus_one(admin)
    domain_after = domain_fingerprint()
    if audit_dataset() != audit or domain_before != domain_after:
        raise ValueError("A medicao alterou os registros do dominio.")
    return {
        "format_version": 1,
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "postgresql": version,
            "python": platform.python_version(),
            "django": django.get_version(),
            "architecture": platform.machine(),
            "settings": settings,
        },
        "dataset": {
            "seed": seed,
            "requested": {"orders": orders, "customers": customers, "products": products},
            **audit,
        },
        "protocol": {
            "warmups_per_query_per_phase": 2,
            "repeats": repeats,
            "cache": "warm; no OS cache reset",
            "phase_order": list(phases),
            "query_order": "seeded shuffle each round",
            "planner_defaults": True,
        },
        "existing_indexes": before_indexes,
        "candidate_indexes": INDEXES,
        "index_builds": builds,
        "queries": {
            name: {"sql": sql, "params": params, "result_sha256": result_hashes[name]}
            for name, (sql, params) in compiled.items()
        },
        "phases": phases,
        "n_plus_one": n_plus_one,
        "domain_sha256_before": domain_before,
        "domain_sha256_after": domain_after,
        "domain_audit_unchanged": True,
        "payment_mode": "SIMULATED_NO_REAL_CHARGE",
    }
