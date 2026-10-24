from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from inventory.models import StockMovement
from orders.exceptions import OrderIntegrityConflict
from orders.lifecycle import approve_simulated_payment, cancel_order, deliver_order, ship_order
from orders.models import Order, OrderItem, Shipment, SimulatedPayment
from orders.services import create_order
from tests.order_fixtures import ADDRESS, build_order_fixtures, order_domain_snapshot
from tests.test_authentication import TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class OrderIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_order_fixtures(cls)

    def setUp(self):
        self.order = create_order(
            user=self.user,
            items=[{"product_id": self.product.pk, "quantity": 3}],
            shipping_address=dict(ADDRESS),
        )

    def assert_rejected_without_repair(self, action):
        before = order_domain_snapshot()
        with self.assertRaises(OrderIntegrityConflict):
            action()
        self.assertEqual(order_domain_snapshot(), before)

    def pay(self):
        return approve_simulated_payment(user=self.admin, order_id=self.order.pk)

    def cancel(self):
        return cancel_order(user=self.user, order_id=self.order.pk)

    def ship(self):
        return ship_order(user=self.admin, order_id=self.order.pk)

    def deliver(self):
        return deliver_order(user=self.admin, order_id=self.order.pk)

    def test_empty_items_or_wrong_total_block_payment_and_cancellation(self):
        for tamper in (
            lambda: Order.objects.filter(pk=self.order.pk).update(total=Decimal("1.00")),
            lambda: OrderItem.objects.filter(order=self.order).delete(),
        ):
            with transaction.atomic():
                tamper()
                self.assert_rejected_without_repair(self.pay)
                self.assert_rejected_without_repair(self.cancel)
                transaction.set_rollback(True)

    def test_missing_wrong_quantity_wrong_actor_and_extra_reservation_are_rejected(self):
        reservation = StockMovement.objects.filter(order=self.order, movement_type="RESERVATION")
        for tamper in (
            lambda: reservation.delete(),
            lambda: reservation.update(quantity_delta=-2),
            lambda: reservation.update(performed_by=self.admin),
            lambda: StockMovement.objects.create(
                order=self.order,
                product=self.second,
                performed_by=self.user,
                movement_type="RESERVATION",
                quantity_delta=-1,
                reason="Historico ficticio invalido",
            ),
        ):
            with transaction.atomic():
                tamper()
                self.assert_rejected_without_repair(self.pay)
                self.assert_rejected_without_repair(self.cancel)
                transaction.set_rollback(True)

    def test_release_before_cancellation_is_rejected(self):
        StockMovement.objects.create(
            order=self.order,
            product=self.product,
            performed_by=self.user,
            movement_type="RELEASE",
            quantity_delta=3,
            reason="Historico ficticio invalido",
        )
        self.assert_rejected_without_repair(self.pay)
        self.assert_rejected_without_repair(self.cancel)

    def test_pending_order_with_payment_or_shipment_is_not_silently_repaired(self):
        for tamper in (
            lambda: SimulatedPayment.objects.create(
                order=self.order, amount=self.order.total, approved_at=timezone.now()
            ),
            lambda: Shipment.objects.create(order=self.order, shipped_at=timezone.now()),
        ):
            with transaction.atomic():
                tamper()
                self.assert_rejected_without_repair(self.pay)
                self.assert_rejected_without_repair(self.cancel)
                transaction.set_rollback(True)

    def test_paid_order_missing_payment_or_with_wrong_amount_date_is_not_repaired(self):
        self.pay()
        payment = SimulatedPayment.objects.filter(order=self.order)
        for tamper in (
            lambda: payment.delete(),
            lambda: payment.update(amount=Decimal("1.00")),
            lambda: payment.update(approved_at=timezone.now() + timedelta(hours=1)),
        ):
            with transaction.atomic():
                tamper()
                self.assert_rejected_without_repair(self.pay)
                self.assert_rejected_without_repair(self.ship)
                transaction.set_rollback(True)

    def test_paid_order_with_unexpected_shipment_cannot_be_sent(self):
        self.pay()
        Shipment.objects.create(order=self.order, shipped_at=timezone.now())
        self.assert_rejected_without_repair(self.ship)

    def test_missing_or_mismatched_shipment_blocks_repeated_ship_and_delivery(self):
        self.pay()
        self.ship()
        shipment = Shipment.objects.filter(order=self.order)
        for tamper in (
            lambda: shipment.delete(),
            lambda: shipment.update(shipped_at=timezone.now() + timedelta(minutes=1)),
        ):
            with transaction.atomic():
                tamper()
                self.assert_rejected_without_repair(self.ship)
                self.assert_rejected_without_repair(self.deliver)
                transaction.set_rollback(True)

    def test_delivered_order_with_missing_delivery_date_is_not_repaired_on_repeat(self):
        self.pay()
        self.ship()
        self.deliver()
        Shipment.objects.filter(order=self.order).update(delivered_at=None)
        self.assert_rejected_without_repair(self.deliver)
        self.assert_rejected_without_repair(self.pay)

    def test_cancelled_order_with_missing_wrong_release_is_not_released_again(self):
        self.cancel()
        release = StockMovement.objects.filter(order=self.order, movement_type="RELEASE")
        for tamper in (
            lambda: release.delete(),
            lambda: release.update(quantity_delta=2),
            lambda: release.update(performed_by=self.admin),
            lambda: release.update(created_at=self.order.created_at),
        ):
            with transaction.atomic():
                tamper()
                self.assert_rejected_without_repair(self.cancel)
                transaction.set_rollback(True)

    def test_http_integrity_conflict_does_not_expose_internal_diagnostics(self):
        Order.objects.filter(pk=self.order.pk).update(total=Decimal("1.00"))
        before = order_domain_snapshot()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.admin)}")
        response = client.post(f"/api/orders/{self.order.pk}/simulated-payment/", {}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "order_integrity_conflict")
        self.assertNotIn("items_or_total", str(response.data))
        self.assertEqual(order_domain_snapshot(), before)
