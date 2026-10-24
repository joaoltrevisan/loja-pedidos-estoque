from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404

from catalog.models import Product
from common.limits import MAX_STOCK_QUANTITY
from common.validation import clean_text, require_admin, validate_id
from orders.exceptions import OrderConflict

from .models import Stock, StockMovement


def change_stock(*, user, product_id, movement_type, quantity_delta, reason):
    require_admin(user)
    validate_id(product_id)
    reason = clean_text(reason, "reason", max_length=500)
    if (
        type(quantity_delta) is not int
        or not -MAX_STOCK_QUANTITY <= quantity_delta <= MAX_STOCK_QUANTITY
        or quantity_delta == 0
    ):
        raise ValidationError(
            {"quantity_delta": ["Informe inteiro nao zero no intervalo permitido."]}
        )
    if movement_type not in (StockMovement.Type.ENTRY, StockMovement.Type.ADJUSTMENT) or (
        movement_type == StockMovement.Type.ENTRY and quantity_delta < 0
    ):
        raise ValidationError(
            {
                "movement_type": [
                    "Entrada exige quantidade positiva; ajuste exige quantidade nao zero."
                ]
            }
        )
    with transaction.atomic():
        # Mesma ordem de compras/cancelamentos: produto antes de estoque.
        if not Product.objects.select_for_update().filter(pk=product_id).exists():
            raise Http404("Produto nao encontrado.")
        try:
            stock = Stock.objects.select_for_update().get(product_id=product_id)
        except Stock.DoesNotExist as error:
            raise OrderConflict("stock_unavailable", "Estoque nao inicializado.") from error
        new_quantity = stock.available_quantity + quantity_delta
        if not 0 <= new_quantity <= MAX_STOCK_QUANTITY:
            raise OrderConflict(
                "stock_limit_exceeded", "Saldo resultante fora do intervalo permitido."
            )
        stock.available_quantity = new_quantity
        stock.save(update_fields=["available_quantity", "updated_at"])
        movement = StockMovement.objects.create(
            product_id=product_id,
            performed_by_id=user.pk,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            reason=reason,
        )
        return stock, movement
