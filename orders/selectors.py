from accounts.permissions import is_customer, is_store_admin

from .models import Order


def orders_visible_to(user):
    """Aplicar antes de listar OU buscar por ID; permissao de objeto nao filtra listas."""
    orders = Order.objects.select_related("customer")
    if is_store_admin(user):
        return orders
    if is_customer(user):
        return orders.filter(customer__user_id=user.pk)
    return orders.none()
