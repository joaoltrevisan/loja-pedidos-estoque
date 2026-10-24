from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import User
from catalog.models import Product
from inventory.services import change_stock
from orders.models import Order, Shipment, SimulatedPayment
from reports import selectors
from reports.periods import REPORT_TZ, ReportPeriod
from tests.order_fixtures import order_domain_snapshot
from tests.report_fixtures import build_report_fixtures, instant, make_report_order

START, END = date(2026, 1, 1), date(2026, 2, 1)


class ReportSelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_report_fixtures(cls)

    def revenue(self, **kwargs):
        return selectors.revenue_report(user=self.admin, start=START, end=END, **kwargs)

    def test_daily_revenue_uses_approval_bounds_and_fills_empty_days(self):
        result = self.revenue()
        self.assertEqual(result["total"], Decimal("107.70"))
        self.assertEqual(result["paid_orders"], 2)
        self.assertEqual(len(result["series"]), 31)
        self.assertEqual(
            result["series"][0],
            {"period_start": START, "amount": Decimal("77.70"), "paid_orders": 1},
        )
        self.assertEqual(result["series"][1]["amount"], Decimal("30.00"))
        self.assertTrue(all(row["amount"] == 0 for row in result["series"][2:]))
        self.assertEqual(sum(row["amount"] for row in result["series"]), result["total"])
        self.assertEqual(result["payment_mode"], "SIMULATED_NO_REAL_CHARGE")

    def test_monthly_revenue_uses_calendar_months_and_partial_period(self):
        result = selectors.revenue_report(
            user=self.admin, start=date(2025, 12, 31), end=date(2026, 2, 2), group_by="month"
        )
        self.assertEqual(
            [r["period_start"] for r in result["series"]], [date(2025, 12, 1), START, END]
        )
        self.assertEqual(
            [r["amount"] for r in result["series"]],
            [Decimal("0.10"), Decimal("107.70"), Decimal("0.10")],
        )
        self.assertEqual(result["total"], Decimal("107.90"))

    def test_end_minus_microsecond_is_included_exact_end_is_excluded(self):
        payment = self.at_end.simulated_payment
        just_before = instant("2026-02-01T00:00:00") - timedelta(microseconds=1)
        Order.objects.filter(pk=self.at_end.pk).update(paid_at=just_before)
        SimulatedPayment.objects.filter(pk=payment.pk).update(approved_at=just_before)
        result = self.revenue()
        self.assertEqual(result["total"], Decimal("107.80"))
        self.assertEqual(result["series"][-1]["amount"], Decimal("0.10"))

    def test_midnight_grouping_uses_sao_paulo_not_utc_or_active_timezone(self):
        when = instant("2026-01-01T23:59:59")
        Order.objects.filter(pk=self.second_sale.pk).update(paid_at=when, shipped_at=when)
        SimulatedPayment.objects.filter(order=self.second_sale).update(approved_at=when)
        Shipment.objects.filter(order=self.second_sale).update(shipped_at=when)
        with timezone.override("Asia/Tokyo"):
            result = self.revenue()
        self.assertEqual(result["series"][0]["amount"], Decimal("107.70"))
        self.assertEqual(result["series"][1]["amount"], Decimal("0.00"))

    def test_average_ticket_counts_payments_once_despite_multiple_items(self):
        result = selectors.average_ticket_report(user=self.admin, start=START, end=END)
        self.assertEqual(
            (result["total"], result["paid_orders"], result["average_ticket"]),
            (Decimal("107.70"), 2, Decimal("53.85")),
        )

    def test_average_ticket_rounds_half_up_without_float(self):
        for day, price in ((1, "1.00"), (2, "1.01")):
            Product.objects.filter(pk=self.second.pk).update(price=price)
            make_report_order(
                self,
                created=instant(f"2026-03-0{day}T00:00:00"),
                paid=instant(f"2026-03-0{day}T01:00:00"),
                items=[{"product_id": self.second.pk, "quantity": 1}],
            )
        result = selectors.average_ticket_report(
            user=self.admin, start=date(2026, 3, 1), end=date(2026, 3, 3)
        )
        self.assertEqual(result["average_ticket"], Decimal("1.01"))
        self.assertEqual((result["total"], result["paid_orders"]), (Decimal("2.01"), 2))

    def test_product_ranking_uses_historical_prices_groups_by_id_and_includes_inactive(self):
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        rows = list(
            selectors.top_products(user=self.admin, start=START, end=END).order_by("product_id")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0],
            {
                "product_id": self.product.pk,
                "sku": "REPORT-RENAMED",
                "name": "Nome atual ficticio",
                "units_sold": 4,
                "simulated_revenue": Decimal("107.50"),
            },
        )
        self.assertEqual(
            (rows[1]["units_sold"], rows[1]["simulated_revenue"]), (2, Decimal("0.20"))
        )
        self.assertEqual(sum(r["simulated_revenue"] for r in rows), Decimal("107.70"))

    def test_customer_ranking_has_exact_sums_and_no_private_contact_fields(self):
        rows = list(
            selectors.top_customers(user=self.admin, start=START, end=END).order_by("customer_id")
        )
        self.assertEqual(
            [r["simulated_revenue"] for r in rows], [Decimal("77.70"), Decimal("30.00")]
        )
        self.assertEqual([r["paid_orders"] for r in rows], [1, 1])
        self.assertEqual(set(rows[0]), {"customer_id", "name", "paid_orders", "simulated_revenue"})

    def test_low_stock_includes_threshold_zero_and_excludes_inactive(self):
        rows = list(selectors.low_stock(user=self.admin, threshold=5))
        self.assertEqual([r.product_id for r in rows], [self.product.pk])
        self.assertFalse(selectors.low_stock(user=self.admin, threshold=0).exists())
        change_stock(
            user=self.admin,
            product_id=self.product.pk,
            movement_type="ADJUSTMENT",
            quantity_delta=-5,
            reason="Contagem ficticia para teste de limite.",
        )
        self.assertTrue(selectors.low_stock(user=self.admin, threshold=0).exists())
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertFalse(selectors.low_stock(user=self.admin, threshold=5).exists())

    def test_status_counts_use_order_creation_and_include_all_zero_states(self):
        result = selectors.orders_by_status_report(user=self.admin, start=START, end=END)
        self.assertEqual(result["date_basis"], "order_created_at")
        self.assertEqual(result["total_orders"], 4)
        self.assertEqual(
            {r["status"]: r["count"] for r in result["statuses"]},
            {"PENDING_PAYMENT": 1, "PAID": 1, "SHIPPED": 1, "DELIVERED": 0, "CANCELLED": 1},
        )

    def test_oldest_pending_age_is_inclusive_and_does_not_expire_or_mutate(self):
        before = order_domain_snapshot()
        now = instant("2026-01-04T10:00:00")
        with patch("reports.selectors.timezone.now", return_value=now):
            self.assertEqual(
                list(selectors.oldest_pending(user=self.admin, min_age_hours=24)), [self.pending]
            )
            self.assertFalse(selectors.oldest_pending(user=self.admin, min_age_hours=25).exists())
        with patch("reports.selectors.timezone.now", return_value=instant("2026-01-03T09:59:59")):
            self.assertFalse(selectors.oldest_pending(user=self.admin).exists())
        self.assertEqual(order_domain_snapshot(), before)

    def test_empty_period_returns_zero_series_zero_average_and_empty_rankings(self):
        start, end = date(2027, 1, 1), date(2027, 1, 3)
        revenue = selectors.revenue_report(user=self.admin, start=start, end=end)
        self.assertEqual(revenue["total"], Decimal("0.00"))
        self.assertEqual(len(revenue["series"]), 2)
        self.assertEqual(
            selectors.average_ticket_report(user=self.admin, start=start, end=end)[
                "average_ticket"
            ],
            Decimal("0.00"),
        )
        self.assertFalse(selectors.top_products(user=self.admin, start=start, end=end).exists())
        self.assertFalse(selectors.top_customers(user=self.admin, start=start, end=end).exists())
        statuses = selectors.orders_by_status_report(user=self.admin, start=start, end=end)
        self.assertEqual(statuses["total_orders"], 0)
        self.assertEqual(len(statuses["statuses"]), 5)

    def test_all_read_selectors_preserve_the_entire_domain(self):
        before = order_domain_snapshot()
        self.revenue()
        selectors.average_ticket_report(user=self.admin, start=START, end=END)
        selectors.orders_by_status_report(user=self.admin, start=START, end=END)
        list(selectors.top_products(user=self.admin, start=START, end=END))
        list(selectors.top_customers(user=self.admin, start=START, end=END))
        list(selectors.low_stock(user=self.admin, threshold=10))
        list(selectors.oldest_pending(user=self.admin))
        self.assertEqual(order_domain_snapshot(), before)

    def test_services_recheck_active_admin_even_for_stale_instances(self):
        functions = [
            lambda u: selectors.revenue_report(user=u, start=START, end=END),
            lambda u: selectors.average_ticket_report(user=u, start=START, end=END),
            lambda u: selectors.top_products(user=u, start=START, end=END),
            lambda u: selectors.top_customers(user=u, start=START, end=END),
            lambda u: selectors.low_stock(user=u, threshold=5),
            lambda u: selectors.orders_by_status_report(user=u, start=START, end=END),
            lambda u: selectors.oldest_pending(user=u),
        ]
        for user in (None, AnonymousUser(), self.user):
            for function in functions:
                with self.assertRaises(PermissionDenied):
                    function(user)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        for function in functions:
            with self.assertRaises(PermissionDenied):
                function(self.admin)
        User.objects.filter(pk=self.admin.pk).update(is_staff=True, is_active=False)
        with self.assertRaises(PermissionDenied):
            self.revenue()

    def test_direct_selectors_reject_invalid_period_group_threshold_and_age(self):
        for start, end in (
            (END, START),
            (START, START),
            (START, START + timedelta(days=367)),
            ("2026-01-01", END),
            (datetime(2026, 1, 1), END),
        ):
            with self.assertRaises(ValidationError):
                selectors.revenue_report(user=self.admin, start=start, end=end)
        with self.assertRaises(ValidationError):
            self.revenue(group_by="year")
        for value in (True, "5", -1, 2147483648):
            with self.assertRaises(ValidationError):
                selectors.low_stock(user=self.admin, threshold=value)
        for value in (True, "1", -1, 87601):
            with self.assertRaises(ValidationError):
                selectors.oldest_pending(user=self.admin, min_age_hours=value)

    def test_revenue_uses_one_data_aggregate_for_total_count_and_series(self):
        with CaptureQueriesContext(connection) as queries:
            self.revenue()
        payment_queries = [
            q for q in queries.captured_queries if 'FROM "orders_simulatedpayment"' in q["sql"]
        ]
        self.assertEqual(len(payment_queries), 1)
        self.assertIn("GROUP BY", payment_queries[0]["sql"])

    @override_settings(TIME_ZONE="UTC")
    def test_period_supports_leap_year_and_historical_dst_boundary(self):
        leap = ReportPeriod(date(2024, 2, 28), date(2024, 3, 1))
        self.assertEqual((leap.end - leap.start).days, 2)
        dst = ReportPeriod(date(2018, 11, 4), date(2018, 11, 5))
        self.assertEqual(dst.bounds[1] - dst.bounds[0], timedelta(hours=23))
        self.assertEqual(dst.bounds[0].astimezone(REPORT_TZ).date(), dst.start)

    def test_sql_day_grouping_at_historical_dst_start_matches_period_bounds(self):
        for paid in ("2018-11-03T23:59:59", "2018-11-04T01:00:00", "2018-11-05T00:00:00"):
            make_report_order(
                self,
                created=instant("2018-11-03T10:00:00"),
                paid=instant(paid),
                items=[{"product_id": self.second.pk, "quantity": 1}],
            )
        result = selectors.revenue_report(
            user=self.admin, start=date(2018, 11, 4), end=date(2018, 11, 5)
        )
        self.assertEqual(result["total"], Decimal("0.10"))
        self.assertEqual(
            result["series"],
            [{"period_start": date(2018, 11, 4), "amount": Decimal("0.10"), "paid_orders": 1}],
        )

    def test_maximum_period_fills_leap_year_and_empty_months(self):
        daily = selectors.revenue_report(
            user=self.admin, start=date(2024, 1, 1), end=date(2025, 1, 1)
        )
        self.assertEqual(len(daily["series"]), 366)
        monthly = selectors.revenue_report(
            user=self.admin, start=date(2024, 1, 1), end=date(2025, 1, 1), group_by="month"
        )
        self.assertEqual(len(monthly["series"]), 12)
        self.assertTrue(all(r["amount"] == 0 for r in monthly["series"]))
