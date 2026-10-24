from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import Customer
from catalog.models import Product
from common.limits import MAX_ORDER_TOTAL
from inventory.models import Stock, StockMovement

from .exceptions import OrderConflict
from .models import Order, OrderItem
from .validation import validate_order_input


def create_order(*, user, items, shipping_address):
    if not user or not user.is_authenticated:
        raise PermissionDenied("Somente clientes podem criar pedidos.")
    # Reconsulta o papel atual; chamadas diretas ao servico tambem sao protegidas.
    customer = Customer.objects.filter(
        user_id=user.pk, user__is_active=True, user__is_staff=False
    ).first()
    if customer is None:
        raise PermissionDenied("Somente clientes podem criar pedidos.")
    items, address = validate_order_input(items=items, shipping_address=shipping_address)
    quantities = {item["product_id"]: item["quantity"] for item in items}
    product_ids = sorted(quantities)

    with transaction.atomic():
        # A ordem global e: produtos por ID, depois estoques por produto.
        # Bloquear o produto estabiliza preco, SKU, nome e atividade da compra.
        products = list(
            Product.objects.select_for_update().filter(pk__in=product_ids).order_by("id")
        )
        if len(products) != len(product_ids):
            raise ValidationError({"items": ["Um ou mais produtos nao existem."]})
        for product in products:
            if not product.is_active:
                raise OrderConflict("product_inactive", f"Produto {product.pk} esta inativo.")
        stocks = list(
            Stock.objects.select_for_update()
            .filter(product_id__in=product_ids)
            .order_by("product_id")
        )
        if len(stocks) != len(product_ids):
            raise OrderConflict("stock_unavailable", "Estoque nao inicializado para algum produto.")
        for stock in stocks:
            if stock.available_quantity < quantities[stock.product_id]:
                raise OrderConflict(
                    "insufficient_stock", f"Estoque insuficiente para o produto {stock.product_id}."
                )
        total = sum((p.price * quantities[p.pk] for p in products), Decimal("0.00"))
        if not total.is_finite() or not Decimal("0.00") < total <= MAX_ORDER_TOTAL:
            raise ValidationError({"items": ["Total fora do limite permitido."]})
        order = Order.objects.create(
            customer=customer,
            total=total,
            **{f"shipping_{key}": value for key, value in address.items()},
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=product,
                    quantity=quantities[product.pk],
                    unit_price=product.price,
                    product_sku=product.sku,
                    product_name=product.name,
                )
                for product in products
            ]
        )
        for stock in stocks:
            stock.available_quantity -= quantities[stock.product_id]
            stock.save(update_fields=["available_quantity", "updated_at"])
        # Se esta ultima gravacao falhar, pedido, itens e saldos tambem voltam.
        StockMovement.objects.bulk_create(
            [
                StockMovement(
                    product=product,
                    order=order,
                    performed_by_id=customer.user_id,
                    movement_type=StockMovement.Type.RESERVATION,
                    quantity_delta=-quantities[product.pk],
                    reason="Reserva na criacao do pedido.",
                )
                for product in products
            ]
        )
        return order
