"""Transicoes sob bloqueio: pedido -> produtos -> estoques, sem cobranca real."""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from accounts.models import Customer, User
from catalog.models import Product
from common.limits import MAX_STOCK_QUANTITY
from inventory.models import Stock, StockMovement

from .exceptions import OrderConflict, OrderIntegrityConflict
from .integrity import inspect_order_history
from .models import Order, Shipment, SimulatedPayment
from .validation import MAX_PRODUCT_ID, validate_tracking_code


@dataclass(frozen=True)
class OrderTransitionResult:
    # Objetos lidos/escritos sob o mesmo bloqueio: nao buscar relacionamentos
    # depois do commit e misturar a resposta com uma transicao concorrente.
    order: Order
    simulated_payment: SimulatedPayment | None
    shipment: Shipment | None


def _require_admin(user):
    if (
        not user
        or not user.is_authenticated
        or not User.objects.filter(pk=user.pk, is_active=True, is_staff=True).exists()
    ):
        raise PermissionDenied("Operacao exclusiva de administrador.")


def _require_customer(user):
    customer = None
    if user and user.is_authenticated:
        customer = Customer.objects.filter(
            user_id=user.pk, user__is_active=True, user__is_staff=False
        ).first()
    if customer is None:
        raise PermissionDenied("Operacao exclusiva de cliente.")
    return customer


def _locked_order(order_id, *, customer=None):
    if type(order_id) is not int or not 1 <= order_id <= MAX_PRODUCT_ID:
        raise Http404("Pedido nao encontrado.")
    queryset = Order.objects.all()
    if customer is not None:
        queryset = queryset.filter(customer=customer)
    try:
        # Sem JOIN: nao adquirir bloqueios de usuario/cliente por acidente.
        return queryset.select_for_update().get(pk=order_id)
    except Order.DoesNotExist as error:
        raise Http404("Pedido nao encontrado.") from error


def approve_simulated_payment(*, user, order_id):
    _require_admin(user)
    with transaction.atomic():
        order = _locked_order(order_id)
        history = inspect_order_history(order)
        if order.status == Order.Status.CANCELLED:
            raise OrderConflict(
                "invalid_transition", "Pedido cancelado nao pode receber pagamento."
            )
        if order.status != Order.Status.PENDING_PAYMENT:
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        at = timezone.now()
        payment = SimulatedPayment.objects.create(
            order=order, amount=order.total, approved_at=at, is_simulated=True
        )
        order.status = Order.Status.PAID
        order.paid_at = at
        order.save(update_fields=["status", "paid_at", "updated_at"])
        return OrderTransitionResult(order, payment, None)


def cancel_order(*, user, order_id):
    customer = _require_customer(user)
    with transaction.atomic():
        order = _locked_order(order_id, customer=customer)
        history = inspect_order_history(order)
        if order.status == Order.Status.CANCELLED:
            return OrderTransitionResult(order, None, None)
        if order.status != Order.Status.PENDING_PAYMENT:
            raise OrderConflict("invalid_transition", "Somente pedido pendente pode ser cancelado.")
        quantities = {item.product_id: item.quantity for item in history.items}
        product_ids = sorted(quantities)
        # O produto tambem e necessario para as FKs dos movimentos. Nunca
        # adquirir essa referencia depois de segurar o estoque.
        products = list(
            Product.objects.select_for_update().filter(pk__in=product_ids).order_by("id")
        )
        stocks = list(
            Stock.objects.select_for_update()
            .filter(product_id__in=product_ids)
            .order_by("product_id")
        )
        if len(products) != len(product_ids) or len(stocks) != len(product_ids):
            raise OrderIntegrityConflict("missing_product_or_stock")
        if any(
            stock.available_quantity + quantities[stock.product_id] > MAX_STOCK_QUANTITY
            for stock in stocks
        ):
            raise OrderConflict("stock_capacity_exceeded", "Devolucao excede o limite do estoque.")
        at = timezone.now()
        for stock in stocks:
            stock.available_quantity += quantities[stock.product_id]
            stock.save(update_fields=["available_quantity", "updated_at"])
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    order=order,
                    product_id=product_id,
                    performed_by_id=customer.user_id,
                    movement_type=StockMovement.Type.RELEASE,
                    quantity_delta=quantity,
                    reason="Liberacao por cancelamento do pedido.",
                )
                for product_id, quantity in sorted(quantities.items())
            ]
        )
        order.status = Order.Status.CANCELLED
        order.cancelled_at = at
        order.save(update_fields=["status", "cancelled_at", "updated_at"])
        return OrderTransitionResult(order, None, None)


def ship_order(*, user, order_id, tracking_code=""):
    _require_admin(user)
    tracking_code = validate_tracking_code(tracking_code)
    with transaction.atomic():
        order = _locked_order(order_id)
        history = inspect_order_history(order)
        if order.status in (Order.Status.SHIPPED, Order.Status.DELIVERED):
            if history.shipment.tracking_code != tracking_code:
                raise OrderConflict(
                    "tracking_conflict", "Rastreamento diferente do envio original."
                )
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        if order.status != Order.Status.PAID:
            raise OrderConflict("invalid_transition", "Somente pedido pago pode ser enviado.")
        at = timezone.now()
        shipment = Shipment.objects.create(order=order, tracking_code=tracking_code, shipped_at=at)
        order.status = Order.Status.SHIPPED
        order.shipped_at = at
        order.save(update_fields=["status", "shipped_at", "updated_at"])
        return OrderTransitionResult(order, history.simulated_payment, shipment)


def deliver_order(*, user, order_id):
    _require_admin(user)
    with transaction.atomic():
        order = _locked_order(order_id)
        history = inspect_order_history(order)
        if order.status == Order.Status.DELIVERED:
            return OrderTransitionResult(order, history.simulated_payment, history.shipment)
        if order.status != Order.Status.SHIPPED:
            raise OrderConflict("invalid_transition", "Somente pedido enviado pode ser entregue.")
        at = timezone.now()
        shipment = history.shipment
        shipment.delivered_at = at
        shipment.save(update_fields=["delivered_at"])
        order.status = Order.Status.DELIVERED
        order.delivered_at = at
        order.save(update_fields=["status", "delivered_at", "updated_at"])
        return OrderTransitionResult(order, history.simulated_payment, shipment)
