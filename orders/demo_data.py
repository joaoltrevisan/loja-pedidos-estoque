"""Dataset ficticio usa os servicos; apenas datas/referencias sao fixadas para repetibilidade."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.core.management.base import CommandError
from django.db import connection, transaction

from accounts.models import Customer, User
from catalog.models import Product
from inventory.models import Stock, StockMovement

from .lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from .models import Order, OrderItem, Shipment, SimulatedPayment
from .services import create_order

DEMO_TIME = datetime(2026, 1, 5, 12, tzinfo=UTC)
PRODUCTS = (
    ("DEMO-CADERNO", "Caderno Horizonte (ficticio)", "25.90", 30),
    ("DEMO-CANECA", "Caneca Aurora (ficticia)", "39.90", 20),
    ("DEMO-CANETA", "Caneta Brisa (ficticia)", "4.50", 50),
)
ORDERS = (
    (Order.Status.PENDING_PAYMENT, 0, ((0, 3),)),
    (Order.Status.PAID, 1, ((1, 2),)),
    (Order.Status.SHIPPED, 2, ((0, 1), (2, 2))),
    (Order.Status.DELIVERED, 0, ((1, 1), (2, 3))),
    (Order.Status.CANCELLED, 1, ((0, 2),)),
)


def set_dates(record, at):
    fields = {field.name for field in record._meta.fields}
    dates = {name: at for name in ("created_at", "updated_at") if name in fields}
    type(record).objects.filter(pk=record.pk).update(**dates)


def record_movement(product, delta, kind, actor, at, order=None):
    movement = StockMovement.objects.create(
        product=product,
        quantity_delta=delta,
        movement_type=kind,
        order=order,
        performed_by=actor,
        reason="Demonstracao ficticia reproduzivel; sem operacao real.",
    )
    set_dates(movement, at)
    # A criacao transacional pode ter atualizado outro objeto Stock. Nao use
    # o cache da relacao product.stock ao montar os demais estados da fixture.
    stock = Stock.objects.get(product=product)
    stock.available_quantity += delta
    stock.save(update_fields=["available_quantity", "updated_at"])
    set_dates(stock, at)


@transaction.atomic
def create_demo_dataset(password):
    # Serializa apenas execucoes deste gerador. Nao prova concorrencia de compras.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [81723003])
    domain_models = (
        User,
        Customer,
        Product,
        Stock,
        Order,
        OrderItem,
        SimulatedPayment,
        Shipment,
        StockMovement,
    )
    if any(model.objects.exists() for model in domain_models):
        raise CommandError(
            "O gerador exige uma base de dominio vazia e nao apaga dados existentes."
        )

    admin = User.objects.create_superuser(
        email="admin.demo@example.com",
        name="Administrador Ficticio",
        password=password,
        date_joined=DEMO_TIME,
    )
    customers = []
    for index, name in enumerate(("Ana Modelo", "Bruno Exemplo", "Carla Ficticia"), 1):
        user = User.objects.create_user(
            email=f"cliente{index}.demo@example.com",
            name=name,
            password=password,
            date_joined=DEMO_TIME,
        )
        customer = Customer.objects.create(user=user)
        set_dates(customer, DEMO_TIME)
        customers.append(customer)

    products = []
    for sku, name, price, opening in PRODUCTS:
        product = Product.objects.create(
            sku=sku,
            name=name,
            description="Produto ficticio para demonstracao.",
            price=Decimal(price),
        )
        set_dates(product, DEMO_TIME)
        Stock.objects.create(product=product)
        record_movement(product, opening, StockMovement.Type.ENTRY, admin, DEMO_TIME)
        products.append(product)

    for number, (status, customer_index, lines) in enumerate(ORDERS, 1):
        at = DEMO_TIME + timedelta(days=number)
        customer = customers[customer_index]
        order = create_order(
            user=customer.user,
            items=[
                {"product_id": products[index].pk, "quantity": quantity}
                for index, quantity in lines
            ],
            shipping_address={
                "recipient": customer.user.name,
                "street": "Rua da Demonstracao (ficticia)",
                "number": "123",
                "district": "Bairro Modelo",
                "city": "Sao Paulo",
                "state": "SP",
                "postal_code": "01001000",
            },
        )
        # Somente o gerador fixa as datas para manter a demonstracao reproduzivel.
        set_dates(order, at)
        order.stock_movements.update(created_at=at)
        Stock.objects.filter(product_id__in=[products[index].pk for index, _ in lines]).update(
            updated_at=at
        )

        updates = {"updated_at": at}
        if status == Order.Status.CANCELLED:
            cancel_order(user=customer.user, order_id=order.pk)
            updates["cancelled_at"] = at + timedelta(hours=1)
            order.stock_movements.filter(movement_type=StockMovement.Type.RELEASE).update(
                created_at=updates["cancelled_at"]
            )
            Stock.objects.filter(product_id__in=[products[index].pk for index, _ in lines]).update(
                updated_at=updates["cancelled_at"]
            )
        elif status != Order.Status.PENDING_PAYMENT:
            approve_simulated_payment(user=admin, order_id=order.pk)
            if status in (Order.Status.SHIPPED, Order.Status.DELIVERED):
                ship_order(
                    user=admin, order_id=order.pk, tracking_code=f"SIMULATED-TRACKING-{number:03}"
                )
            if status == Order.Status.DELIVERED:
                deliver_order(user=admin, order_id=order.pk)
            # O servico executou o fluxo com o relogio real. Somente esta fixture
            # reposiciona os eventos para um calendario ficticio fixo, na mesma
            # transacao externa e sem expor esse caminho pela API.
            updates["paid_at"] = at + timedelta(hours=1)
            SimulatedPayment.objects.filter(order=order).update(
                approved_at=updates["paid_at"],
                reference=uuid5(
                    NAMESPACE_URL, f"https://example.com/loja/demo/v1/payment/{number}"
                ),
            )
            if status in (Order.Status.SHIPPED, Order.Status.DELIVERED):
                updates["shipped_at"] = at + timedelta(hours=2)
                if status == Order.Status.DELIVERED:
                    updates["delivered_at"] = at + timedelta(days=1)
                Shipment.objects.filter(order=order).update(
                    shipped_at=updates["shipped_at"],
                    delivered_at=updates.get("delivered_at"),
                )
        updates["updated_at"] = max(
            value for value in updates.values() if isinstance(value, datetime)
        )
        Order.objects.filter(pk=order.pk).update(**updates)
