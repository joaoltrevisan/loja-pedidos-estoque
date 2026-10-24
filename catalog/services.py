from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404

from common.validation import clean_text, require_admin, validate_id
from inventory.models import Stock
from orders.exceptions import OrderConflict

from .models import Product

PRODUCT_FIELDS = {"sku", "name", "description", "price", "is_active"}


def validate_product(data, *, partial=False):
    if not isinstance(data, dict) or set(data) - PRODUCT_FIELDS:
        raise ValidationError({"product": ["Campos de produto invalidos."]})
    if not partial and {"sku", "name", "price"} - set(data):
        raise ValidationError({"product": ["Informe sku, name e price."]})
    clean = {}
    for field, value in data.items():
        if field in ("sku", "name", "description"):
            limit = {"sku": 64, "name": 200, "description": 5000}[field]
            value = clean_text(value, field, max_length=limit, blank=field == "description")
        elif field == "price":
            if not isinstance(value, (str, Decimal)):
                raise ValidationError({field: ["Informe texto decimal ou Decimal."]})
            try:
                value = Decimal(value)
            except InvalidOperation as error:
                raise ValidationError({field: ["Decimal invalido."]}) from error
        elif type(value) is not bool:
            raise ValidationError({field: ["Informe um booleano."]})
        # Validadores do modelo verificam SKU, precisao, finitude e preco positivo.
        if field != "description":
            try:
                value = Product._meta.get_field(field).clean(value, None)
            except ValidationError as error:
                raise ValidationError({field: error.messages}) from error
        clean[field] = value
    return clean


def save_product(*, user, data, product_id=None):
    require_admin(user)
    clean = validate_product(data, partial=product_id is not None)
    if product_id is not None:
        validate_id(product_id)
    try:
        with transaction.atomic():
            if product_id is None:
                product = Product.objects.create(**clean)
                Stock.objects.create(product=product, available_quantity=0)
            else:
                try:
                    product = Product.objects.select_for_update().get(pk=product_id)
                except Product.DoesNotExist as error:
                    raise Http404("Produto nao encontrado.") from error
                for key, value in clean.items():
                    setattr(product, key, value)
                if clean:
                    product.save(update_fields=[*clean, "updated_at"])
            return product
    except IntegrityError as error:
        if (
            getattr(error.__cause__, "diag", None)
            and error.__cause__.diag.constraint_name == "catalog_product_sku_key"
        ):
            raise OrderConflict("sku_conflict", "SKU ja cadastrado.") from error
        raise
