"""Coerencia entre tabelas; chamar mantendo o bloqueio do pedido."""

from dataclasses import dataclass
from decimal import Decimal

from common.limits import MAX_ORDER_ITEMS

from .exceptions import OrderIntegrityConflict
from .models import Order, OrderItem, Shipment, SimulatedPayment


@dataclass(frozen=True)
class OrderHistory:
    items: list[OrderItem]
    simulated_payment: SimulatedPayment | None
    shipment: Shipment | None


def inspect_order_history(order):
    items = list(order.items.order_by("product_id"))
    if not 1 <= len(items) <= MAX_ORDER_ITEMS or order.total != sum(
        (item.subtotal for item in items), Decimal("0.00")
    ):
        raise OrderIntegrityConflict("items_or_total")
    movements = list(order.stock_movements.order_by("product_id", "movement_type"))
    reservations = {m.product_id: m for m in movements if m.movement_type == "RESERVATION"}
    releases = {m.product_id: m for m in movements if m.movement_type == "RELEASE"}
    expected_ids = {item.product_id for item in items}
    if set(reservations) != expected_ids:
        raise OrderIntegrityConflict("reservations_missing_or_extra")
    customer_user_id = order.customer.user_id
    for item in items:
        reserve = reservations[item.product_id]
        if (
            reserve.quantity_delta != -item.quantity
            or reserve.performed_by_id != customer_user_id
            or reserve.created_at < order.created_at
        ):
            raise OrderIntegrityConflict("reservation_mismatch")
    if order.status == Order.Status.CANCELLED:
        if set(releases) != expected_ids:
            raise OrderIntegrityConflict("releases_missing_or_extra")
        for item in items:
            release = releases[item.product_id]
            if (
                release.quantity_delta != item.quantity
                or release.performed_by_id != customer_user_id
                or release.created_at < order.cancelled_at
            ):
                raise OrderIntegrityConflict("release_mismatch")
    elif releases:
        raise OrderIntegrityConflict("release_before_cancellation")

    payment = SimulatedPayment.objects.filter(order=order).first()
    shipment = Shipment.objects.filter(order=order).first()
    paid = order.status in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)
    if paid:
        if (
            payment is None
            or payment.amount != order.total
            or not payment.is_simulated
            or payment.approved_at != order.paid_at
        ):
            raise OrderIntegrityConflict("payment_mismatch")
    elif payment is not None:
        raise OrderIntegrityConflict("unexpected_payment")
    shipped = order.status in (Order.Status.SHIPPED, Order.Status.DELIVERED)
    if shipped:
        if (
            shipment is None
            or shipment.shipped_at != order.shipped_at
            or shipment.delivered_at != order.delivered_at
        ):
            raise OrderIntegrityConflict("shipment_mismatch")
    elif shipment is not None:
        raise OrderIntegrityConflict("unexpected_shipment")
    return OrderHistory(items, payment, shipment)
