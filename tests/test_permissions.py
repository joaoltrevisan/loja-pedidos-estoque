from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Customer, User
from accounts.permissions import CanReadOrder
from catalog.models import Product
from inventory.models import Stock, StockMovement
from orders.models import Order, OrderItem
from orders.selectors import orders_visible_to
from tests.test_authentication import PASSWORD, TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS, ROOT_URLCONF="tests.auth_urls")
class PermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("dono@example.com", PASSWORD, name="Dono Ficticio")
        cls.other = User.objects.create_user("outro@example.com", PASSWORD, name="Outro Ficticio")
        cls.admin = User.objects.create_user(
            "admin@example.com", PASSWORD, name="Admin", is_staff=True
        )
        cls.orphan = User.objects.create_user("semperfil@example.com", PASSWORD, name="Sem Perfil")
        cls.customer = Customer.objects.create(user=cls.owner)
        cls.other_customer = Customer.objects.create(user=cls.other)
        product = Product.objects.create(
            sku="PERMISSION-TEST", name="Ficticio", price=Decimal("2.00")
        )
        Stock.objects.create(product=product, available_quantity=8)
        StockMovement.objects.create(
            product=product,
            performed_by=cls.admin,
            movement_type="ENTRY",
            quantity_delta=10,
            reason="Teste ficticio",
        )
        cls.order = cls.make_order(cls.customer, product)
        cls.other_order = cls.make_order(cls.other_customer, product)

    @classmethod
    def make_order(cls, customer, product):
        order = Order.objects.create(
            customer=customer,
            total=Decimal("2.00"),
            shipping_recipient="Ficticio",
            shipping_street="Rua Imaginaria",
            shipping_number="1",
            shipping_district="Bairro Ficticio",
            shipping_city="Sao Paulo",
            shipping_state="SP",
            shipping_postal_code="01001000",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            unit_price=product.price,
            product_sku=product.sku,
            product_name=product.name,
        )
        StockMovement.objects.create(
            product=product,
            order=order,
            performed_by=customer.user,
            movement_type="RESERVATION",
            quantity_delta=-1,
            reason="Reserva ficticia de teste",
        )
        return order

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def authenticate(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def test_endpoint_roles_customer_admin_anonymous_and_missing_profile(self):
        for user, customer_status, admin_status in (
            (None, 401, 401),
            (self.owner, 200, 403),
            (self.admin, 403, 200),
            (self.orphan, 403, 403),
        ):
            with self.subTest(user=user):
                if user:
                    self.authenticate(user)
                else:
                    self.client.credentials()
                self.assertEqual(self.client.post("/_test/customer/").status_code, customer_status)
                self.assertEqual(self.client.post("/_test/admin/").status_code, admin_status)

    def test_customer_lists_only_own_orders_and_cannot_discover_foreign_detail(self):
        self.authenticate(self.owner)
        self.assertEqual(self.client.get("/_test/orders/").data, [self.order.pk])
        self.assertEqual(self.client.get(f"/_test/orders/{self.order.pk}/").status_code, 200)
        foreign = self.client.get(f"/_test/orders/{self.other_order.pk}/")
        missing = self.client.get("/_test/orders/999999999/")
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.data, missing.data)

    def test_admin_reads_all_orders_without_customer_profile(self):
        self.authenticate(self.admin)
        self.assertEqual(
            self.client.get("/_test/orders/").data, [self.order.pk, self.other_order.pk]
        )
        self.assertEqual(self.client.get(f"/_test/orders/{self.other_order.pk}/").status_code, 200)

    def test_anonymous_and_missing_profile_cannot_read_orders(self):
        self.assertEqual(self.client.get("/_test/orders/").status_code, 401)
        self.authenticate(self.orphan)
        self.assertEqual(self.client.get("/_test/orders/").status_code, 403)
        self.assertEqual(self.client.get("/api/auth/me/").data["role"], "unassigned")

    def test_read_permission_never_grants_mutation_even_to_admin(self):
        for user in (self.owner, self.other, self.admin):
            with self.subTest(user=user):
                self.authenticate(user)
                self.assertEqual(
                    self.client.post(f"/_test/orders/{self.order.pk}/").status_code, 403
                )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "PENDING_PAYMENT")
        self.assertEqual(Stock.objects.get().available_quantity, 8)

    def test_object_permission_denies_foreign_owner_independently_of_query_filter(self):
        request = APIRequestFactory().get("/")
        force_authenticate(request, user=self.owner)
        request = APIView().initialize_request(request)
        permission = CanReadOrder()
        self.assertTrue(permission.has_object_permission(request, None, self.order))
        self.assertFalse(permission.has_object_permission(request, None, self.other_order))

    def test_selector_denies_anonymous_inactive_and_missing_profile(self):
        self.assertFalse(orders_visible_to(AnonymousUser()).exists())
        self.assertFalse(orders_visible_to(self.orphan).exists())
        self.owner.is_active = False
        self.assertFalse(orders_visible_to(self.owner).exists())
        self.admin.is_active = False
        self.assertFalse(orders_visible_to(self.admin).exists())

    def test_admin_privilege_removal_takes_effect_with_existing_token(self):
        self.authenticate(self.admin)
        self.assertEqual(self.client.post("/_test/admin/").status_code, 200)
        User.objects.filter(pk=self.admin.pk).update(is_staff=False)
        self.assertEqual(self.client.post("/_test/admin/").status_code, 403)
        self.assertEqual(self.client.get("/_test/orders/").status_code, 403)

    def test_admin_with_customer_profile_still_cannot_use_customer_only_actions(self):
        Customer.objects.create(user=self.admin)
        self.authenticate(self.admin)
        self.assertEqual(self.client.post("/_test/customer/").status_code, 403)
