"""Consultas de negocio sem escrita; cada agregado usa um unico snapshot SQL."""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

from django.core.exceptions import ValidationError
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from common.limits import MAX_STOCK_QUANTITY
from common.validation import require_admin
from inventory.models import Stock
from orders.models import Order, OrderItem, SimulatedPayment

from .periods import REPORT_TZ, ReportPeriod

PAID_STATES = (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)
ZERO = Decimal("0.00")
SIMULATION_NOTICE = "SIMULADO: sem cobranca real; nao e apuracao contabil ou fiscal."


def paid_payments(period):
    start, end = period.bounds
    return SimulatedPayment.objects.filter(
        approved_at__gte=start,
        approved_at__lt=end,
        order__status__in=PAID_STATES,
        is_simulated=True,
    )


def financial_metadata(period):
    return {
        **period.metadata,
        "currency": "BRL",
        "payment_mode": "SIMULATED_NO_REAL_CHARGE",
        "notice": SIMULATION_NOTICE,
    }


def daily_revenue(period):
    return (
        paid_payments(period)
        .annotate(day=TruncDate("approved_at", tzinfo=REPORT_TZ))
        .values("day")
        .annotate(amount=Sum("amount"), paid_orders=Count("id"))
        .order_by("day")
    )


def revenue_report(*, user, start, end, group_by="day"):
    require_admin(user)
    period = ReportPeriod(start, end)
    if group_by not in ("day", "month"):
        raise ValidationError({"group_by": ["Use day ou month."]})
    daily = list(daily_revenue(period))
    # Ate 366 dias: preencher lacunas e reagrupar meses nao exige carregar pagamentos.
    buckets = {}
    day = start
    while day < end:
        key = day if group_by == "day" else day.replace(day=1)
        buckets.setdefault(key, {"period_start": key, "amount": ZERO, "paid_orders": 0})
        day += timedelta(days=1)
    with localcontext() as context:
        context.prec = 50
        total, count = ZERO, 0
        for row in daily:
            key = row["day"] if group_by == "day" else row["day"].replace(day=1)
            buckets[key]["amount"] += row["amount"]
            buckets[key]["paid_orders"] += row["paid_orders"]
            total += row["amount"]
            count += row["paid_orders"]
    return {
        **financial_metadata(period),
        "group_by": group_by,
        "total": total,
        "paid_orders": count,
        "series": list(buckets.values()),
    }


def average_ticket_report(*, user, start, end):
    require_admin(user)
    period = ReportPeriod(start, end)
    # Somar pagamentos sem juntar itens evita multiplicar um pagamento pelo numero de linhas.
    summary = paid_payments(period).aggregate(
        total=Sum("amount", default=ZERO), paid_orders=Count("id")
    )
    with localcontext() as context:
        context.prec = 50
        average = (
            (summary["total"] / summary["paid_orders"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if summary["paid_orders"]
            else ZERO
        )
    return {**financial_metadata(period), **summary, "average_ticket": average}


def top_products(*, user, start, end):
    require_admin(user)
    period = ReportPeriod(start, end)
    payments = paid_payments(period).values("order_id")
    historical_value = ExpressionWrapper(
        F("quantity") * F("unit_price"), output_field=DecimalField(max_digits=40, decimal_places=2)
    )
    return (
        OrderItem.objects.filter(order_id__in=payments)
        .values("product_id", sku=F("product__sku"), name=F("product__name"))
        .annotate(units_sold=Sum("quantity"), simulated_revenue=Sum(historical_value))
    )


def top_customers(*, user, start, end):
    require_admin(user)
    period = ReportPeriod(start, end)
    return (
        paid_payments(period)
        .values(customer_id=F("order__customer_id"), name=F("order__customer__user__name"))
        .annotate(paid_orders=Count("id"), simulated_revenue=Sum("amount"))
    )


def low_stock(*, user, threshold):
    require_admin(user)
    if type(threshold) is not int or not 0 <= threshold <= MAX_STOCK_QUANTITY:
        raise ValidationError({"threshold": ["Informe inteiro entre 0 e 2147483647."]})
    return Stock.objects.filter(
        product__is_active=True, available_quantity__lte=threshold
    ).select_related("product")


def orders_by_status_report(*, user, start, end):
    require_admin(user)
    period = ReportPeriod(start, end)
    beginning, ending = period.bounds
    grouped = dict(
        Order.objects.filter(created_at__gte=beginning, created_at__lt=ending)
        .values("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )
    rows = [{"status": status, "count": grouped.get(status, 0)} for status in Order.Status.values]
    return {
        **period.metadata,
        "date_basis": "order_created_at",
        "total_orders": sum(row["count"] for row in rows),
        "statuses": rows,
    }


def oldest_pending(*, user, min_age_hours=0):
    require_admin(user)
    if type(min_age_hours) is not int or not 0 <= min_age_hours <= 87600:
        raise ValidationError({"min_age_hours": ["Informe inteiro entre 0 e 87600."]})
    cutoff = timezone.now() - timedelta(hours=min_age_hours)
    return Order.objects.filter(status=Order.Status.PENDING_PAYMENT, created_at__lte=cutoff)
