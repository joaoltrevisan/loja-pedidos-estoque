from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from catalog.models import Product
from tests.order_fixtures import order_domain_snapshot
from tests.report_fixtures import build_report_fixtures, instant, make_report_order

PERIOD = {"start": "2026-01-01", "end": "2026-02-01"}
PERIOD_REPORTS = ("revenue", "average-ticket", "top-products", "top-customers", "orders-by-status")
ALL_REPORTS = (*PERIOD_REPORTS, "low-stock", "oldest-pending")


class ReportAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_report_fixtures(cls)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.auth(self.admin)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def get(self, report, params=None):
        if params is None:
            params = (
                PERIOD
                if report in PERIOD_REPORTS
                else {"threshold": "5"}
                if report == "low-stock"
                else {}
            )
        return self.client.get(f"/api/reports/{report}/", params)

    def test_all_reports_require_authenticated_current_administrator(self):
        for user, expected in ((self.user, 403), (None, 401)):
            self.auth(user) if user else self.client.credentials()
            for report in ALL_REPORTS:
                response = self.get(report)
                self.assertEqual(response.status_code, expected, (report, response.data))
                self.assertEqual(set(response.data), {"code", "detail", "errors"})
        self.auth(self.admin)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        for report in ALL_REPORTS:
            self.assertEqual(self.get(report).status_code, 403)
        User.objects.filter(pk=self.admin.pk).update(is_staff=True, is_active=False)
        self.assertEqual(self.get("revenue").status_code, 401)

    def test_daily_and_monthly_revenue_have_exact_money_and_simulation_notice(self):
        response = self.get("revenue")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total"], "107.70")
        self.assertEqual(response.data["paid_orders"], 2)
        self.assertEqual(response.data["series"][0]["amount"], "77.70")
        self.assertEqual(response.data["series"][1]["amount"], "30.00")
        self.assertEqual(len(response.data["series"]), 31)
        self.assertEqual(response.data["timezone"], "America/Sao_Paulo")
        self.assertEqual(response.data["payment_mode"], "SIMULATED_NO_REAL_CHARGE")
        self.assertIn("nao e apuracao contabil", response.data["notice"])
        month = self.get("revenue", dict(PERIOD, group_by="month"))
        self.assertEqual(
            month.data["series"],
            [{"period_start": "2026-01-01", "amount": "107.70", "paid_orders": 2}],
        )

    def test_average_ticket_does_not_multiply_payments_by_items(self):
        response = self.get("average-ticket")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            (response.data["total"], response.data["paid_orders"], response.data["average_ticket"]),
            ("107.70", 2, "53.85"),
        )
        self.assertEqual(response.data["payment_mode"], "SIMULATED_NO_REAL_CHARGE")

    def test_ranked_products_use_historical_prices_and_preserve_aggregate_groups(self):
        first = self.get("top-products", dict(PERIOD, page_size="1"))
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["count"], 2)
        row = first.data["results"][0]
        self.assertEqual(
            (row["product_id"], row["units_sold"], row["simulated_revenue"]),
            (self.product.pk, 4, "107.50"),
        )
        self.assertEqual(row["sku"], "REPORT-RENAMED")
        second = self.client.get(first.data["next"])
        self.assertEqual(
            (
                second.data["results"][0]["product_id"],
                second.data["results"][0]["simulated_revenue"],
            ),
            (self.second.pk, "0.20"),
        )
        self.assertIsNotNone(second.data["previous"])
        self.assertIsNone(second.data["next"])

    def test_customer_ranking_default_and_allowed_alternative_ordering(self):
        response = self.get("top-customers")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [r["simulated_revenue"] for r in response.data["results"]], ["77.70", "30.00"]
        )
        ordered = self.get("top-customers", dict(PERIOD, ordering="simulated_revenue"))
        self.assertEqual(ordered.data["results"][0]["simulated_revenue"], "30.00")
        self.assertEqual(
            set(ordered.data["results"][0]),
            {"customer_id", "name", "paid_orders", "simulated_revenue"},
        )

    def test_ranking_ties_use_group_identifier_without_splitting_totals(self):
        make_report_order(
            self,
            created=instant("2026-01-03T12:00:00"),
            paid=instant("2026-01-03T13:00:00"),
            items=[{"product_id": self.second.pk, "quantity": 2}],
        )
        response = self.get("top-products")
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [r["product_id"] for r in response.data["results"]], [self.product.pk, self.second.pk]
        )
        self.assertEqual([r["units_sold"] for r in response.data["results"]], [4, 4])

    def test_low_stock_is_inclusive_and_active_only(self):
        response = self.get("low-stock")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["available_quantity"], 5)
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertEqual(self.get("low-stock").data["results"], [])
        self.assertEqual(self.get("low-stock", {"threshold": "0"}).status_code, 200)

    def test_order_status_counts_use_creation_not_payment_date(self):
        response = self.get("orders-by-status")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["total_orders"], 4)
        self.assertEqual(
            {r["status"]: r["count"] for r in response.data["statuses"]},
            {"PENDING_PAYMENT": 1, "PAID": 1, "SHIPPED": 1, "DELIVERED": 0, "CANCELLED": 1},
        )
        self.assertEqual(response.data["date_basis"], "order_created_at")

    def test_oldest_pending_orders_are_deterministic_and_age_bound_is_inclusive(self):
        same = make_report_order(
            self,
            created=instant("2026-01-03T10:00:00"),
            items=[{"product_id": self.second.pk, "quantity": 1}],
        )
        newer = make_report_order(
            self,
            created=instant("2026-01-04T09:00:00"),
            items=[{"product_id": self.second.pk, "quantity": 1}],
        )
        with patch("reports.selectors.timezone.now", return_value=instant("2026-01-04T10:00:00")):
            response = self.get("oldest-pending")
            self.assertEqual(
                [r["id"] for r in response.data["results"]], [self.pending.pk, same.pk, newer.pk]
            )
            aged = self.get("oldest-pending", {"min_age_hours": "24"})
            self.assertEqual([r["id"] for r in aged.data["results"]], [self.pending.pk, same.pk])

    def test_period_parameters_are_required_exact_dates_ordered_and_bounded(self):
        invalid = [
            {},
            {"start": "2026-01-01"},
            dict(PERIOD, start="2026-02-30"),
            dict(PERIOD, start="20260101"),
            dict(PERIOD, start="2026-01-01T00:00:00Z"),
            dict(PERIOD, start="2026-02-01"),
            dict(PERIOD, start="2026-03-01"),
            dict(PERIOD, start="2024-01-01"),
            dict(PERIOD, start="0000-01-01"),
        ]
        for report in PERIOD_REPORTS:
            for params in invalid:
                with self.subTest(report=report, params=params):
                    response = self.get(report, params)
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(self.get("revenue", dict(PERIOD, group_by="year")).status_code, 400)

    def test_all_reports_reject_unknown_and_repeated_parameters(self):
        for report in ALL_REPORTS:
            params = (
                dict(PERIOD)
                if report in PERIOD_REPORTS
                else {"threshold": "5"}
                if report == "low-stock"
                else {}
            )
            params["foo"] = "bar"
            self.assertEqual(self.get(report, params).status_code, 400, report)
            self.assertEqual(
                self.client.get(
                    f"/api/reports/{report}/?start=2026-01-01&start=2026-01-02&end=2026-02-01"
                ).status_code,
                400,
            )

    def test_list_query_limits_and_sorting_are_strict(self):
        for report in ("top-products", "top-customers", "low-stock", "oldest-pending"):
            base = (
                dict(PERIOD)
                if report.startswith("top-")
                else {"threshold": "5"}
                if report == "low-stock"
                else {}
            )
            for extra in (
                {"page": "1.0"},
                {"page_size": "1.00"},
                {"page_size": "101"},
                {"page": "0"},
                {"ordering": "?"},
                {"ordering": "id,id"},
                {"ordering": "product__price"},
            ):
                response = self.get(report, {**base, **extra})
                self.assertEqual(response.status_code, 400, (report, extra, response.data))
        for report, field, values in (
            ("low-stock", "threshold", ("1.0", "-1", "2147483648", "")),
            ("oldest-pending", "min_age_hours", ("1.0", "-1", "87601", "")),
        ):
            for value in values:
                self.assertEqual(self.get(report, {field: value}).status_code, 400)
        self.assertEqual(self.get("low-stock", {}).status_code, 400)

    def test_empty_results_have_explicit_zero_and_stable_shapes(self):
        empty = {"start": "2027-01-01", "end": "2027-01-03"}
        revenue = self.get("revenue", empty)
        self.assertEqual(revenue.data["total"], "0.00")
        self.assertEqual(len(revenue.data["series"]), 2)
        self.assertEqual(self.get("average-ticket", empty).data["average_ticket"], "0.00")
        for report in ("top-products", "top-customers"):
            self.assertEqual(
                self.get(report, empty).data,
                {"count": 0, "next": None, "previous": None, "results": []},
            )
        self.assertEqual(self.get("orders-by-status", empty).data["total_orders"], 0)

    def test_get_head_options_are_private_and_no_report_accepts_writes(self):
        before = order_domain_snapshot()
        for report in ALL_REPORTS:
            response = self.get(report)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIn("no-store", response["Cache-Control"])
            params = (
                PERIOD
                if report in PERIOD_REPORTS
                else {"threshold": "5"}
                if report == "low-stock"
                else {}
            )
            self.assertEqual(self.client.head(f"/api/reports/{report}/", params).status_code, 200)
            self.assertEqual(self.client.options(f"/api/reports/{report}/").status_code, 200)
            for method in (
                self.client.post,
                self.client.patch,
                self.client.put,
                self.client.delete,
            ):
                self.assertEqual(
                    method(f"/api/reports/{report}/", {}, format="json").status_code, 405
                )
        self.assertEqual(order_domain_snapshot(), before)

    def test_rankings_and_lists_do_not_issue_one_query_per_result(self):
        for report in ("top-products", "top-customers", "low-stock", "oldest-pending"):
            with CaptureQueriesContext(connection) as queries:
                response = self.get(report)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertLessEqual(len(queries), 5, (report, len(queries)))

    def test_openapi_documents_all_reports_permissions_examples_and_period_limits(self):
        schema = SchemaGenerator().get_schema(public=True)
        validate_schema(schema)
        for report in ALL_REPORTS:
            operation = schema["paths"][f"/api/reports/{report}/"]["get"]
            self.assertIn("Perfil autorizado: administrador", operation["description"])
            self.assertEqual(operation["security"], [{"jwtAuth": []}])
            self.assertIn("examples", operation["responses"]["200"]["content"]["application/json"])
            self.assertNotIn("post", schema["paths"][f"/api/reports/{report}/"])
            if report in PERIOD_REPORTS:
                required = {p["name"] for p in operation["parameters"] if p.get("required")}
                self.assertTrue({"start", "end"} <= required)
        self.assertEqual(schema["info"]["version"], "0.8.0")
