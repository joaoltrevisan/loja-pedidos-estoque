from decimal import Decimal

from accounts.models import Customer, User
from catalog.models import Product
from inventory.models import Stock, StockMovement
from orders.models import Order, OrderItem, Shipment, SimulatedPayment
from tests.test_authentication import PASSWORD

ADDRESS = {
    "recipient": "Cliente Ficticio",
    "street": "Rua Imaginaria",
    "number": "123",
    "district": "Bairro Modelo",
    "city": "Sao Paulo",
    "state": "SP",
    "postal_code": "01001000",
}


def build_order_fixtures(target):
    target.user = User.objects.create_user("compra@example.com", PASSWORD, name="Cliente Ficticio")
    target.other = User.objects.create_user("outro@example.com", PASSWORD, name="Outro Ficticio")
    target.admin = User.objects.create_user(
        "admin@example.com", PASSWORD, name="Admin", is_staff=True
    )
    target.customer = Customer.objects.create(user=target.user)
    Customer.objects.create(user=target.other)
    target.product = Product.objects.create(
        sku="ORDER-A", name="Caderno Ficticio", price=Decimal("25.90")
    )
    target.second = Product.objects.create(
        sku="ORDER-B", name="Peca Ficticia", price=Decimal("0.10")
    )
    for product, quantity in ((target.product, 10), (target.second, 20)):
        Stock.objects.create(product=product, available_quantity=quantity)
        StockMovement.objects.create(
            product=product,
            performed_by=target.admin,
            movement_type=StockMovement.Type.ENTRY,
            quantity_delta=quantity,
            reason="Entrada ficticia de teste.",
        )


def order_domain_snapshot():
    return {
        model.__name__: list(model.objects.order_by("pk").values())
        for model in (Product, Stock, StockMovement, Order, OrderItem, SimulatedPayment, Shipment)
    }
