"""Carga ficticia deterministica pelas mesmas regras transacionais da API."""

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.db import connection, transaction

from accounts.models import Customer, User
from catalog.models import Product
from catalog.services import save_product
from inventory.models import Stock, StockMovement
from inventory.services import change_stock
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order, OrderItem, Shipment, SimulatedPayment
from orders.services import create_order

DOMAIN = (
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
OPENING = datetime(2023, 12, 31, tzinfo=UTC)
START = datetime(2024, 1, 1, tzinfo=UTC)


def require_isolated_database(expected_name):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        actual = cursor.fetchone()[0]
    if not expected_name.startswith("loja_bench_") or actual != expected_name:
        raise ValueError("Benchmark exige o banco descartavel criado por esta execucao.")


def validate_sizes(orders, customers, products, seed):
    for value, low, high in ((orders, 1, 100000), (customers, 2, 2000), (products, 10, 5000)):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(
                "Volumes invalidos: pedidos 1..100000, clientes 2..2000, produtos 10..5000."
            )
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError("Seed deve ser inteiro entre 0 e 2147483647.")


@transaction.atomic
def create_dataset(
    *, expected_name, orders=20000, customers=500, products=1000, seed=42, progress=print
):
    validate_sizes(orders, customers, products, seed)
    require_isolated_database(expected_name)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [81723009])
    if any(model.objects.exists() for model in DOMAIN):
        raise ValueError("A base deve estar vazia; o gerador nao apaga dados.")
    rng = random.Random(seed)
    admin = User.objects.create_superuser(
        email="admin.benchmark@example.com",
        name="Administrador Ficticio",
        password=None,
        date_joined=OPENING,
    )
    buyers = []
    for number in range(customers):
        user = User.objects.create_user(
            email=f"cliente{number:04}.benchmark@example.com",
            name=f"Cliente Ficticio {number:04}",
            password=None,
            date_joined=OPENING,
        )
        buyer = Customer.objects.create(user=user)
        buyers.append(buyer)
    Customer.objects.update(created_at=OPENING, updated_at=OPENING)
    catalog = []
    sold_products = products * 9 // 10
    for number in range(products):
        product = save_product(
            user=admin,
            data={
                "sku": f"BENCH-PROD-{number:05}",
                "name": f"Produto Ficticio {number:05}",
                "description": "Carga ficticia de desempenho; pagamentos sempre simulados.",
                "price": Decimal(100 + number * 137 % 9900) / 100,
            },
        )
        opening = 1000000 if number < sold_products else number % 50
        if opening:
            change_stock(
                user=admin,
                product_id=product.pk,
                movement_type="ENTRY",
                quantity_delta=opening,
                reason="Entrada ficticia do benchmark.",
            )
        catalog.append(product)
    Product.objects.update(created_at=OPENING, updated_at=OPENING)
    StockMovement.objects.update(created_at=OPENING)
    dates = {}
    for number in range(orders):
        buyer = buyers[0 if rng.random() < 0.20 else rng.randrange(1, customers)]
        count = rng.randint(1, 3)
        chosen = {0} if rng.random() < 0.35 else set()
        while len(chosen) < count:
            chosen.add(rng.randrange(sold_products))
        order = create_order(
            user=buyer.user,
            items=[
                {"product_id": catalog[i].pk, "quantity": rng.randint(1, 5)} for i in sorted(chosen)
            ],
            shipping_address={
                "recipient": buyer.user.name,
                "street": "Rua Ficticia",
                "number": "123",
                "district": "Bairro Modelo",
                "city": "Sao Paulo",
                "state": "SP",
                "postal_code": "01001000",
            },
        )
        bucket = number % 100
        if bucket >= 95:
            cancel_order(user=buyer.user, order_id=order.pk)
        elif bucket >= 5:
            approve_simulated_payment(user=admin, order_id=order.pk)
            if bucket >= 35:
                ship_order(
                    user=admin, order_id=order.pk, tracking_code=f"SIMULATED-BENCH-{number:06}"
                )
            if bucket >= 60:
                deliver_order(user=admin, order_id=order.pk)
        day = rng.randrange(700, 731) if rng.random() < 0.30 else rng.randrange(731)
        at = START + timedelta(days=day, minutes=rng.randrange(1440))
        dates[order.pk] = (at, number)
        if (number + 1) % 1000 == 0:
            progress(f"Pedidos ficticios preparados: {number + 1}/{orders}")

    # Somente a fixture reposiciona datas, depois dos servicos, na mesma transacao.
    order_rows = list(Order.objects.order_by("id"))
    for order in order_rows:
        at, _ = dates[order.pk]
        order.created_at = at
        order.paid_at = at + timedelta(hours=1) if order.paid_at else None
        order.cancelled_at = at + timedelta(hours=1) if order.cancelled_at else None
        order.shipped_at = at + timedelta(hours=2) if order.shipped_at else None
        order.delivered_at = at + timedelta(days=1) if order.delivered_at else None
        order.updated_at = max(
            x
            for x in (at, order.paid_at, order.cancelled_at, order.shipped_at, order.delivered_at)
            if x is not None
        )
    Order.objects.bulk_update(
        order_rows,
        ["created_at", "updated_at", "paid_at", "cancelled_at", "shipped_at", "delivered_at"],
        batch_size=250,
    )
    payments = list(SimulatedPayment.objects.all())
    for payment in payments:
        at, number = dates[payment.order_id]
        payment.approved_at = at + timedelta(hours=1)
        payment.reference = uuid5(NAMESPACE_URL, f"https://example.com/loja/benchmark/v1/{number}")
    SimulatedPayment.objects.bulk_update(payments, ["approved_at", "reference"], batch_size=250)
    shipments = list(Shipment.objects.all())
    delivered = {o.pk for o in order_rows if o.status == Order.Status.DELIVERED}
    for shipment in shipments:
        at, _ = dates[shipment.order_id]
        shipment.shipped_at = at + timedelta(hours=2)
        shipment.delivered_at = at + timedelta(days=1) if shipment.order_id in delivered else None
    Shipment.objects.bulk_update(shipments, ["shipped_at", "delivered_at"], batch_size=250)
    movements = list(StockMovement.objects.exclude(order_id=None))
    latest = {p.pk: OPENING for p in catalog}
    for movement in movements:
        at, _ = dates[movement.order_id]
        movement.created_at = at + (
            timedelta(hours=1) if movement.movement_type == "RELEASE" else timedelta()
        )
        latest[movement.product_id] = max(latest[movement.product_id], movement.created_at)
    StockMovement.objects.bulk_update(movements, ["created_at"], batch_size=500)
    stocks = list(Stock.objects.all())
    for stock in stocks:
        stock.updated_at = latest[stock.product_id]
    Stock.objects.bulk_update(stocks, ["updated_at"], batch_size=500)
    # Parte do catalogo muda apos as vendas: valores financeiros continuam historicos.
    for product in catalog[::10]:
        save_product(
            user=admin,
            product_id=product.pk,
            data={"price": product.price + Decimal("5.00"), "is_active": False},
        )
    Product.objects.update(updated_at=datetime(2026, 1, 3, tzinfo=UTC))
    return admin
