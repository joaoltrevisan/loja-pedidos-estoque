"""Validacao de entrada reutilizada pela API e pelo servico, sem consultas ao banco."""

from django.core.exceptions import ValidationError

from common.limits import MAX_ITEM_QUANTITY, MAX_ORDER_ITEMS

from .models import Order, Shipment

ADDRESS_FIELDS = (
    "recipient",
    "street",
    "number",
    "complement",
    "district",
    "city",
    "state",
    "postal_code",
)
MAX_PRODUCT_ID = 9223372036854775807


def validate_order_input(*, items, shipping_address):
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ORDER_ITEMS:
        raise ValidationError({"items": [f"Informe de 1 a {MAX_ORDER_ITEMS} itens."]})
    seen = set()
    clean_items = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {"product_id", "quantity"}:
            raise ValidationError({"items": [f"Item {index}: use apenas product_id e quantity."]})
        product_id, quantity = item["product_id"], item["quantity"]
        if type(product_id) is not int or not 1 <= product_id <= MAX_PRODUCT_ID:
            raise ValidationError(
                {"items": [f"Item {index}: product_id deve ser inteiro positivo."]}
            )
        if type(quantity) is not int or not 1 <= quantity <= MAX_ITEM_QUANTITY:
            raise ValidationError(
                {"items": [f"Item {index}: quantity deve ser inteiro de 1 a {MAX_ITEM_QUANTITY}."]}
            )
        if product_id in seen:
            raise ValidationError({"items": [f"Produto {product_id} repetido."]})
        seen.add(product_id)
        clean_items.append({"product_id": product_id, "quantity": quantity})

    if not isinstance(shipping_address, dict):
        raise ValidationError({"shipping_address": ["Informe um objeto com o endereco."]})
    required = set(ADDRESS_FIELDS) - {"complement"}
    if set(shipping_address) - set(ADDRESS_FIELDS) or required - set(shipping_address):
        raise ValidationError(
            {
                "shipping_address": [
                    "Campos obrigatorios: recipient, street, number, district, city, state, "
                    "postal_code; "
                    "complement e opcional. Outros campos nao sao permitidos."
                ]
            }
        )
    clean_address = {}
    for key in ADDRESS_FIELDS:
        value = shipping_address.get(key, "")
        if not isinstance(value, str):
            raise ValidationError({"shipping_address": [f"{key}: informe um texto."]})
        try:
            # Reutiliza comprimentos, obrigatoriedade, UF e CEP do modelo.
            clean_address[key] = Order._meta.get_field(f"shipping_{key}").clean(value.strip(), None)
        except ValidationError as error:
            raise ValidationError(
                {"shipping_address": [f"{key}: {m}" for m in error.messages]}
            ) from error
        clean_value = clean_address[key]
        if "\x00" in clean_value:
            raise ValidationError({"shipping_address": [f"{key}: caractere nulo nao permitido."]})
        try:
            clean_value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValidationError(
                {"shipping_address": [f"{key}: texto Unicode invalido."]}
            ) from error
    return clean_items, clean_address


def validate_tracking_code(value):
    if not isinstance(value, str):
        raise ValidationError({"tracking_code": ["Informe um texto."]})
    try:
        value = Shipment._meta.get_field("tracking_code").clean(value.strip(), None)
    except ValidationError as error:
        raise ValidationError({"tracking_code": error.messages}) from error
    if "\x00" in value:
        raise ValidationError({"tracking_code": ["Caractere nulo nao permitido."]})
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValidationError({"tracking_code": ["Texto Unicode invalido."]}) from error
    return value
