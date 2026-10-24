from datetime import datetime
from unittest.mock import patch

from catalog.models import Product
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.services import create_order
from reports.periods import REPORT_TZ
from tests.order_fixtures import ADDRESS, build_order_fixtures


def instant(value):
    return datetime.fromisoformat(value).replace(tzinfo=REPORT_TZ)


def make_report_order(target, *, created, items, paid=None, user=None, state="PAID"):
    with patch("django.utils.timezone.now", return_value=created):
        order = create_order(user=user or target.user, items=items, shipping_address=ADDRESS)
    if paid is not None:
        with patch("django.utils.timezone.now", return_value=paid):
            approve_simulated_payment(user=target.admin, order_id=order.pk)
            if state in ("SHIPPED", "DELIVERED"):
                ship_order(user=target.admin, order_id=order.pk, tracking_code="SIMULATED-REPORT")
            if state == "DELIVERED":
                deliver_order(user=target.admin, order_id=order.pk)
    return order


def build_report_fixtures(target):
    build_order_fixtures(target)
    target.first_sale = make_report_order(
        target,
        created=instant("2025-12-31T10:00:00"),
        items=[{"product_id": target.product.pk, "quantity": 3}],
        paid=instant("2026-01-01T00:00:00"),
        state="DELIVERED",
    )
    Product.objects.filter(pk=target.product.pk).update(price="29.80")
    target.second_sale = make_report_order(
        target,
        created=instant("2026-01-01T12:00:00"),
        items=[
            {"product_id": target.product.pk, "quantity": 1},
            {"product_id": target.second.pk, "quantity": 2},
        ],
        paid=instant("2026-01-02T00:00:00"),
        state="SHIPPED",
        user=target.other,
    )
    target.before = make_report_order(
        target,
        created=instant("2025-12-30T10:00:00"),
        items=[{"product_id": target.second.pk, "quantity": 1}],
        paid=instant("2025-12-31T23:59:59.999999"),
    )
    target.at_end = make_report_order(
        target,
        created=instant("2026-01-05T10:00:00"),
        items=[{"product_id": target.second.pk, "quantity": 1}],
        paid=instant("2026-02-01T00:00:00"),
    )
    target.pending = make_report_order(
        target,
        created=instant("2026-01-03T10:00:00"),
        items=[{"product_id": target.product.pk, "quantity": 1}],
    )
    target.cancelled = make_report_order(
        target,
        created=instant("2026-01-04T10:00:00"),
        items=[{"product_id": target.second.pk, "quantity": 2}],
    )
    with patch("django.utils.timezone.now", return_value=instant("2026-01-04T11:00:00")):
        cancel_order(user=target.user, order_id=target.cancelled.pk)
    # Catalogo posterior nao pode reprecificar os itens dos pedidos anteriores.
    Product.objects.filter(pk=target.product.pk).update(
        price="99.99", sku="REPORT-RENAMED", name="Nome atual ficticio"
    )
