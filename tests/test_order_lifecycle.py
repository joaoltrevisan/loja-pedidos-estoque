import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.http import Http404
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Customer, User
from catalog.models import Product
from common.limits import MAX_STOCK_QUANTITY
from inventory.models import Stock, StockMovement
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Shipment, SimulatedPayment
from orders.serializers import OrderTransitionSerializer
from orders.services import create_order
from tests.order_fixtures import ADDRESS, build_order_fixtures, order_domain_snapshot
from tests.test_authentication import TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class OrderLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_order_fixtures(cls)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.order = create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": 3}],
            shipping_address=dict(ADDRESS),
        )

    def post(self, action, *, user=None, order_id=None, data=None):
        if user is None:
            self.client.credentials()
        else:
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        pk = self.order.pk if order_id is None else order_id
        return self.client.post(
            f"/api/orders/{pk}/{action}/", {} if data is None else data, format="json"
        )

    def pay(self):
        return approve_simulated_payment(user=self.admin, order_id=self.order.pk)

    def ship(self, tracking_code="SIMULATED-001"):
        return ship_order(user=self.admin, order_id=self.order.pk, tracking_code=tracking_code)

    def deliver(self):
        return deliver_order(user=self.admin, order_id=self.order.pk)

    def assert_ledger(self):
        for stock in Stock.objects.all():
            self.assertEqual(
                stock.available_quantity,
                stock.product.movements.aggregate(total=Sum("quantity_delta"))["total"],
            )

    def test_payment_uses_order_total_and_does_not_deduct_stock_twice(self):
        before_stocks = list(Stock.objects.order_by("pk").values())
        before_movements = list(StockMovement.objects.order_by("pk").values())
        response = self.post("simulated-payment", user=self.admin)
        self.assertEqual(response.status_code, 200, response.data)
        payment = SimulatedPayment.objects.get()
        self.order.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("77.70"))
        self.assertEqual(payment.approved_at, self.order.paid_at)
        self.assertTrue(payment.is_simulated)
        self.assertEqual(self.order.status, "PAID")
        self.assertEqual(response.data["simulated_payment"]["amount"], "77.70")
        self.assertTrue(response.data["simulated_payment"]["is_simulated"])
        self.assertEqual(response.data["order"]["payment_mode"], "SIMULATED_NO_REAL_CHARGE")
        self.assertIsNone(response.data["shipment"])
        self.assertEqual(list(Stock.objects.order_by("pk").values()), before_stocks)
        self.assertEqual(list(StockMovement.objects.order_by("pk").values()), before_movements)
        self.assertIn("no-store", response["Cache-Control"])

    def test_payment_repeat_preserves_reference_dates_and_updated_at(self):
        first = self.post("simulated-payment", user=self.admin)
        before = order_domain_snapshot()
        second = self.post("simulated-payment", user=self.admin)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data, second.data)
        self.assertEqual(order_domain_snapshot(), before)

    def test_payment_repeat_after_shipping_and_delivery_preserves_current_state(self):
        original = self.pay().simulated_payment
        self.ship()
        for expected in ("SHIPPED", "DELIVERED"):
            if expected == "DELIVERED":
                self.deliver()
            before = order_domain_snapshot()
            response = self.post("simulated-payment", user=self.admin)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["order"]["status"], expected)
            self.assertEqual(
                response.data["simulated_payment"]["reference"], str(original.reference)
            )
            self.assertEqual(order_domain_snapshot(), before)

    def test_cancel_returns_stock_records_owner_and_repeats_without_changes(self):
        first = self.post("cancel", user=self.user)
        self.assertEqual(first.status_code, 200, first.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "CANCELLED")
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 10)
        release = self.order.stock_movements.get(movement_type="RELEASE")
        self.assertEqual((release.quantity_delta, release.performed_by_id), (3, self.user.pk))
        self.assertGreaterEqual(release.created_at, self.order.cancelled_at)
        before = order_domain_snapshot()
        second = self.post("cancel", user=self.user)
        self.assertEqual(first.data, second.data)
        self.assertEqual(order_domain_snapshot(), before)
        self.assertFalse(SimulatedPayment.objects.exists() or Shipment.objects.exists())
        self.assert_ledger()

    def test_cancel_multiple_products_even_if_catalog_has_changed(self):
        order = create_order(
            user=self.user,
            items=[
                {"product_id": self.second.pk, "quantity": 2},
                {"product_id": self.product.pk, "quantity": 1},
            ],
            shipping_address=dict(ADDRESS),
        )
        Product.objects.filter(pk__in=[self.product.pk, self.second.pk]).update(
            is_active=False, price=Decimal("30.00")
        )
        result = cancel_order(user=self.user, order_id=order.pk)
        self.assertEqual(result.order.status, "CANCELLED")
        self.assertEqual(order.stock_movements.filter(movement_type="RELEASE").count(), 2)
        self.assertEqual(Stock.objects.get(product=self.product).available_quantity, 7)
        self.assertEqual(Stock.objects.get(product=self.second).available_quantity, 20)
        self.assert_ledger()

    def test_paid_shipped_and_delivered_cannot_be_cancelled(self):
        self.pay()
        for state in ("PAID", "SHIPPED", "DELIVERED"):
            if state == "SHIPPED":
                self.ship()
            elif state == "DELIVERED":
                self.deliver()
            before = order_domain_snapshot()
            response = self.post("cancel", user=self.user)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "invalid_transition")
            self.assertEqual(order_domain_snapshot(), before)

    def test_cancelled_order_rejects_payment_shipping_and_delivery(self):
        cancel_order(user=self.user, order_id=self.order.pk)
        before = order_domain_snapshot()
        for action in ("simulated-payment", "ship", "deliver"):
            response = self.post(action, user=self.admin)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "invalid_transition")
        self.assertEqual(order_domain_snapshot(), before)

    def test_shipping_delivery_and_repeats_preserve_stock_and_dates(self):
        self.pay()
        stocks = list(Stock.objects.order_by("pk").values())
        movements = list(StockMovement.objects.order_by("pk").values())
        first = self.post("ship", user=self.admin, data={"tracking_code": " SIMULATED-001 "})
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["shipment"]["tracking_code"], "SIMULATED-001")
        self.assertEqual(first.data["order"]["shipped_at"], first.data["shipment"]["shipped_at"])
        before = order_domain_snapshot()
        self.assertEqual(
            self.post("ship", user=self.admin, data={"tracking_code": "SIMULATED-001"}).data,
            first.data,
        )
        self.assertEqual(order_domain_snapshot(), before)
        delivered = self.post("deliver", user=self.admin)
        self.assertEqual(delivered.status_code, 200)
        self.assertEqual(
            delivered.data["order"]["delivered_at"], delivered.data["shipment"]["delivered_at"]
        )
        before = order_domain_snapshot()
        self.assertEqual(self.post("deliver", user=self.admin).data, delivered.data)
        self.assertEqual(
            self.post("ship", user=self.admin, data={"tracking_code": "SIMULATED-001"}).data,
            delivered.data,
        )
        self.assertEqual(order_domain_snapshot(), before)
        self.assertEqual(list(Stock.objects.order_by("pk").values()), stocks)
        self.assertEqual(list(StockMovement.objects.order_by("pk").values()), movements)

    def test_shipping_tracking_is_optional_but_cannot_be_replaced(self):
        self.pay()
        first = self.post("ship", user=self.admin)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["shipment"]["tracking_code"], "")
        before = order_domain_snapshot()
        response = self.post("ship", user=self.admin, data={"tracking_code": "OTHER"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "tracking_conflict")
        self.assertEqual(order_domain_snapshot(), before)

    def test_ship_before_payment_and_deliver_before_shipping_are_rejected(self):
        before = order_domain_snapshot()
        for action in ("ship", "deliver"):
            self.assertEqual(self.post(action, user=self.admin).status_code, 409)
        self.assertEqual(order_domain_snapshot(), before)
        self.pay()
        before = order_domain_snapshot()
        self.assertEqual(self.post("deliver", user=self.admin).status_code, 409)
        self.assertEqual(order_domain_snapshot(), before)

    def test_role_and_ownership_authorization_apply_to_actual_endpoints(self):
        before = order_domain_snapshot()
        for action in ("simulated-payment", "ship", "deliver", "cancel"):
            self.assertEqual(self.post(action).status_code, 401)
        for action in ("simulated-payment", "ship", "deliver"):
            self.assertEqual(self.post(action, user=self.user).status_code, 403)
            self.assertEqual(self.post(action, user=self.other).status_code, 403)
        self.assertEqual(self.post("cancel", user=self.admin).status_code, 403)
        Customer.objects.create(user=self.admin)
        self.assertEqual(self.post("cancel", user=self.admin).status_code, 403)
        foreign = self.post("cancel", user=self.other)
        missing = self.post("cancel", user=self.other, order_id=9223372036854775807)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.data, missing.data)
        self.assertEqual(order_domain_snapshot(), before)

    def test_repeated_actions_do_not_bypass_permissions(self):
        self.pay()
        self.assertEqual(self.post("simulated-payment", user=self.user).status_code, 403)
        self.ship()
        self.assertEqual(self.post("ship", user=self.user).status_code, 403)
        self.deliver()
        self.assertEqual(self.post("deliver", user=self.user).status_code, 403)
        order = create_order(
            user=self.user,
            items=[{"product_id": self.second.pk, "quantity": 1}],
            shipping_address=dict(ADDRESS),
        )
        cancel_order(user=self.user, order_id=order.pk)
        self.assertEqual(self.post("cancel", user=self.other, order_id=order.pk).status_code, 404)

    def test_protected_action_fields_are_rejected_without_changes(self):
        before = order_domain_snapshot()
        for action in ("simulated-payment", "ship", "deliver", "cancel"):
            actor = self.user if action == "cancel" else self.admin
            for field in (
                "amount",
                "total",
                "status",
                "customer_id",
                "is_simulated",
                "reference",
                "paid_at",
                "delivered_at",
            ):
                response = self.post(action, user=actor, data={field: "changed"})
                self.assertEqual(response.status_code, 400, (action, field, response.data))
        self.assertEqual(order_domain_snapshot(), before)

    def test_tracking_types_limits_null_and_surrogate_are_rejected(self):
        self.pay()
        before = order_domain_snapshot()
        for value in (None, 12, True, "x" * 101, "a\x00b", "a\ud800b"):
            with self.subTest(value=repr(value)):
                self.client.credentials(
                    HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.admin)}"
                )
                response = self.client.post(
                    f"/api/orders/{self.order.pk}/ship/",
                    json.dumps({"tracking_code": value}, ensure_ascii=True).encode("ascii"),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                with self.assertRaises(ValidationError):
                    ship_order(user=self.admin, order_id=self.order.pk, tracking_code=value)
        self.assertEqual(order_domain_snapshot(), before)

    def test_service_rechecks_admin_and_customer_roles(self):
        for service in (approve_simulated_payment, ship_order, deliver_order):
            for actor in (None, AnonymousUser(), self.user):
                with self.assertRaises(PermissionDenied):
                    service(user=actor, order_id=self.order.pk)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        with self.assertRaises(PermissionDenied):
            self.pay()
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            cancel_order(user=self.user, order_id=self.order.pk)

    def test_invalid_order_ids_are_safe_not_found_in_services(self):
        for value in (None, True, "1", -1, 0, 9223372036854775808):
            for service, actor in (
                (approve_simulated_payment, self.admin),
                (cancel_order, self.user),
            ):
                with self.subTest(value=value), self.assertRaises(Http404):
                    service(user=actor, order_id=value)

    def test_cancellation_overflow_is_atomic_and_does_not_discard_units(self):
        Stock.objects.filter(product=self.product).update(available_quantity=MAX_STOCK_QUANTITY)
        StockMovement.objects.create(
            product=self.product,
            performed_by=self.admin,
            movement_type="ADJUSTMENT",
            quantity_delta=MAX_STOCK_QUANTITY - 7,
            reason="Limite ficticio para testar devolucao",
        )
        before = order_domain_snapshot()
        response = self.post("cancel", user=self.user)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "stock_capacity_exceeded")
        self.assertEqual(order_domain_snapshot(), before)
        self.assert_ledger()

    def test_cancellation_missing_stock_signals_integrity_conflict(self):
        Stock.objects.filter(product=self.product).delete()
        before = order_domain_snapshot()
        response = self.post("cancel", user=self.user)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "order_integrity_conflict")
        self.assertEqual(order_domain_snapshot(), before)

    def test_all_transitions_roll_back_when_order_save_fails(self):
        operations = (
            lambda: self.pay(),
            lambda: cancel_order(user=self.user, order_id=self.order.pk),
            lambda: self.ship(),
            lambda: self.deliver(),
        )
        for index, operation in enumerate(operations):
            if index == 2:
                self.pay()
            if index == 3:
                self.ship()
            before = order_domain_snapshot()
            with patch("orders.lifecycle.Order.save", side_effect=RuntimeError("Falha controlada")):
                with self.assertRaisesMessage(RuntimeError, "Falha controlada"):
                    operation()
            self.assertEqual(order_domain_snapshot(), before)
        self.assert_ledger()

    def test_response_snapshot_does_not_mix_a_later_delivery(self):
        self.pay()
        shipped = self.ship()
        self.deliver()
        old_response = OrderTransitionSerializer(shipped).data
        self.assertEqual(old_response["order"]["status"], "SHIPPED")
        self.assertIsNone(old_response["shipment"]["delivered_at"])
        self.assertIsNone(old_response["order"]["delivered_at"])

    def test_action_routes_only_accept_post_and_json_objects(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.admin)}")
        url = f"/api/orders/{self.order.pk}/simulated-payment/"
        for method in (self.client.get, self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(url).status_code, 405)
        self.assertEqual(self.client.post(url, [], format="json").status_code, 400)
        self.assertEqual(
            self.client.post(
                url, "x=1", content_type="application/x-www-form-urlencoded"
            ).status_code,
            415,
        )
