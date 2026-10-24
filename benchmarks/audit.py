"""Conferencia em conjuntos, sem executar consultas por pedido."""

from datetime import UTC

from django.db import connection
from django.db.models import Count, Max, Min, Sum
from django.db.models.functions import TruncMonth

from catalog.models import Product
from orders.models import Order, OrderItem

from .dataset import DOMAIN

CHECKS = {
    "stock_ledger": """SELECT count(*) FROM catalog_product p
        LEFT JOIN inventory_stock s ON s.product_id=p.id
        LEFT JOIN (SELECT product_id,sum(quantity_delta) AS balance FROM inventory_stockmovement
                   GROUP BY product_id) m ON m.product_id=p.id
        WHERE s.id IS NULL OR s.available_quantity<>coalesce(m.balance,0)""",
    "order_totals": """SELECT count(*) FROM orders_order o LEFT JOIN
        (SELECT order_id,sum(quantity*unit_price) AS total FROM orders_orderitem
         GROUP BY order_id) i
        ON i.order_id=o.id WHERE i.total IS NULL OR i.total<>o.total""",
    "payments": """SELECT count(*) FROM orders_order o
        LEFT JOIN orders_simulatedpayment p ON p.order_id=o.id
        WHERE ((o.status IN ('PAID','SHIPPED','DELIVERED')) IS DISTINCT FROM (p.id IS NOT NULL))
        OR (p.id IS NOT NULL AND (p.amount<>o.total OR NOT p.is_simulated
                                OR p.approved_at IS DISTINCT FROM o.paid_at))""",
    "shipments": """SELECT count(*) FROM orders_order o
        LEFT JOIN orders_shipment s ON s.order_id=o.id
        WHERE ((o.status IN ('SHIPPED','DELIVERED')) IS DISTINCT FROM (s.id IS NOT NULL))
        OR (s.id IS NOT NULL AND (s.shipped_at IS DISTINCT FROM o.shipped_at
                                OR s.delivered_at IS DISTINCT FROM o.delivered_at))""",
    "reservations": """SELECT count(*) FROM orders_orderitem i
        JOIN orders_order o ON o.id=i.order_id
        JOIN accounts_customer c ON c.id=o.customer_id LEFT JOIN inventory_stockmovement m
        ON m.order_id=i.order_id AND m.product_id=i.product_id AND m.movement_type='RESERVATION'
        WHERE m.id IS NULL OR m.quantity_delta<>-i.quantity OR m.performed_by_id<>c.user_id
        OR m.created_at<o.created_at""",
    "releases": """SELECT count(*) FROM orders_orderitem i
        JOIN orders_order o ON o.id=i.order_id
        JOIN accounts_customer c ON c.id=o.customer_id LEFT JOIN inventory_stockmovement m
        ON m.order_id=i.order_id AND m.product_id=i.product_id AND m.movement_type='RELEASE'
        WHERE ((o.status='CANCELLED') IS DISTINCT FROM (m.id IS NOT NULL))
        OR (m.id IS NOT NULL AND (m.quantity_delta<>i.quantity OR m.performed_by_id<>c.user_id
                                OR m.created_at<o.cancelled_at))""",
    "extra_movements": """SELECT count(*) FROM inventory_stockmovement m
        LEFT JOIN orders_orderitem i
        ON i.order_id=m.order_id AND i.product_id=m.product_id
        WHERE m.order_id IS NOT NULL AND i.id IS NULL""",
}


def audit_dataset():
    with connection.cursor() as cursor:
        checks = {}
        for name, query in CHECKS.items():
            cursor.execute(query)
            checks[name] = cursor.fetchone()[0]
    if any(checks.values()):
        raise ValueError(f"Invariantes violadas na carga: {checks}")
    return {
        "violations": checks,
        "counts": {model._meta.label: model.objects.count() for model in DOMAIN},
        "statuses": list(
            Order.objects.values("status").annotate(count=Count("id")).order_by("status")
        ),
        "dates": Order.objects.aggregate(first=Min("created_at"), last=Max("created_at")),
        "top_customers": list(
            Order.objects.values("customer_id")
            .annotate(count=Count("id"))
            .order_by("-count", "customer_id")[:5]
        ),
        "months_utc": list(
            Order.objects.annotate(month=TruncMonth("created_at", tzinfo=UTC))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        ),
        "item_quantities": list(
            OrderItem.objects.values("quantity").annotate(count=Count("id")).order_by("quantity")
        ),
        "top_products": list(
            OrderItem.objects.values("product_id")
            .annotate(lines=Count("id"), units=Sum("quantity"))
            .order_by("-lines", "product_id")[:5]
        ),
        "inactive_products": Product.objects.filter(is_active=False).count(),
    }
