from datetime import timedelta
from unittest.mock import patch

import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import Customer, User
from accounts.services import register_customer, update_profile

TEST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
PASSWORD = "Ficticio-Cliente-914!"


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "cliente@example.com", PASSWORD, name="Cliente Ficticio"
        )
        cls.customer = Customer.objects.create(user=cls.user, phone="11000000000")
        cls.other = User.objects.create_user("outro@example.com", PASSWORD, name="Outro Ficticio")
        Customer.objects.create(user=cls.other)
        cls.admin = User.objects.create_user(
            "admin@example.com", PASSWORD, name="Admin Ficticio", is_staff=True
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def register(self, **overrides):
        data = {
            "email": " NOVO@EXAMPLE.COM ",
            "name": "Novo Ficticio",
            "password": PASSWORD,
            "phone": "11000000001",
        }
        data.update(overrides)
        return self.client.post("/api/auth/register/", data, format="json")

    def login(self, **overrides):
        data = {"email": self.user.email, "password": PASSWORD}
        data.update(overrides)
        return self.client.post("/api/auth/token/", data, format="json")

    def authenticate(self, user=None):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user or self.user)}"
        )

    def refresh(self, token):
        return self.client.post("/api/auth/token/refresh/", {"refresh": str(token)}, format="json")

    def test_register_creates_customer_with_hashed_password_and_no_privileges(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="novo@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.customer.phone, "11000000001")
        self.assertEqual(
            response.data,
            {
                "id": user.pk,
                "email": user.email,
                "name": user.name,
                "phone": user.customer.phone,
                "role": "customer",
            },
        )
        self.assertNotIn("password", response.data)
        self.assertIn("no-store", response["Cache-Control"])

    def test_register_rejects_duplicate_case_insensitive_email(self):
        response = self.register(email=" CLIENTE@EXAMPLE.COM ")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data["errors"])
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(Customer.objects.count(), 2)

    def test_register_rejects_weak_passwords_using_framework_validators(self):
        for password in ("abc", "password", "123456789012", "novo@example.com"):
            with self.subTest(password=password):
                response = self.register(password=password)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("password", response.data["errors"])
        self.assertFalse(User.objects.filter(email="novo@example.com").exists())

    def test_register_rejects_privilege_and_other_protected_fields(self):
        for field in (
            "is_staff",
            "is_superuser",
            "is_active",
            "groups",
            "user_permissions",
            "role",
            "id",
            "customer",
            "user",
            "status",
            "total",
            "unit_price",
        ):
            with self.subTest(field=field):
                cache.clear()
                response = self.register(**{field: True})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data["errors"])
        self.assertEqual(User.objects.count(), 3)

    def test_register_validates_required_types_lengths_and_email(self):
        for data in (
            {"email": "invalid"},
            {"email": ""},
            {"name": " \t"},
            {"name": 123},
            {"name": "a" * 151},
            {"phone": "0" * 21},
            {"phone": False},
            {"password": "a" * 129},
            {"password": None},
        ):
            with self.subTest(data=data):
                cache.clear()
                self.assertEqual(self.register(**data).status_code, 400)
        self.assertEqual(
            self.client.post("/api/auth/register/", {}, format="json").status_code, 400
        )

    def test_password_whitespace_is_preserved_between_registration_and_login(self):
        password = "  Ficticio-Portfolio-419!  "
        self.assertEqual(self.register(password=password).status_code, 201)
        self.assertEqual(self.login(email="novo@example.com", password=password).status_code, 200)
        self.assertEqual(
            self.login(email="novo@example.com", password=password.strip()).status_code, 401
        )

    def test_customer_failure_rolls_back_registration_user(self):
        with patch("accounts.services.Customer.save", side_effect=RuntimeError("falha controlada")):
            with self.assertRaises(RuntimeError):
                register_customer(email="rollback@example.com", name="Rollback", password=PASSWORD)
        self.assertFalse(User.objects.filter(email="rollback@example.com").exists())

    def test_login_accepts_normalized_email_and_issues_typed_expiring_tokens(self):
        response = self.login(email=" CLIENTE@EXAMPLE.COM ")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data), {"access", "refresh"})
        access, refresh = (
            AccessToken(response.data["access"]),
            RefreshToken(response.data["refresh"]),
        )
        self.assertEqual(access["user_id"], str(self.user.pk))
        self.assertEqual(access["exp"] - access["iat"], 300)
        self.assertEqual(refresh["exp"] - refresh["iat"], 86400)
        self.assertNotIn("is_staff", access)
        self.assertNotIn("email", access)
        self.assertIn("no-store", response["Cache-Control"])

    def test_login_invalid_unknown_and_inactive_have_same_error(self):
        invalid = self.login(password="Errada-914!")
        unknown = self.login(email="ausente@example.com")
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        inactive = self.login()
        for response in (invalid, unknown, inactive):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data, invalid.data)
            self.assertIn("no-store", response["Cache-Control"])

    def test_login_uses_same_unicode_email_equivalence_as_unique_constraint(self):
        first = self.register(email="a@ı.example", password="Primeiro-Ficticio-419!")
        second = self.register(email="a@i.example", password="Segundo-Ficticio-719!")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        for email, password, expected_id in (
            ("a@ı.example", "Primeiro-Ficticio-419!", first.data["id"]),
            ("A@I.EXAMPLE", "Segundo-Ficticio-719!", second.data["id"]),
        ):
            with self.subTest(email=email):
                response = self.login(email=email, password=password)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(AccessToken(response.data["access"])["user_id"], str(expected_id))
        self.assertEqual(
            self.login(email="a@i.example", password="Primeiro-Ficticio-419!").status_code, 401
        )

    def test_login_rejects_extra_fields(self):
        self.assertEqual(self.login(is_staff=True).status_code, 400)

    def test_profile_requires_access_token_and_returns_only_own_data(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.authenticate()
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.user.pk)
        self.assertEqual(set(response.data), {"id", "email", "name", "phone", "role"})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.get(f"/api/auth/me/{self.other.pk}/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/auth/me/?id={self.other.pk}").data["id"], self.user.pk
        )

    def test_profile_update_normalizes_email_preserves_other_user_and_can_login(self):
        self.authenticate()
        response = self.client.patch(
            "/api/auth/me/",
            {"email": " NOVOLOGIN@EXAMPLE.COM ", "name": "Nome Atualizado", "phone": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.user.email, "novologin@example.com")
        self.assertEqual(self.user.name, "Nome Atualizado")
        self.assertEqual(self.user.customer.phone, "")
        self.assertEqual(self.other.name, "Outro Ficticio")
        self.assertTrue(self.user.check_password(PASSWORD))
        self.assertEqual(self.login(email="novologin@example.com").status_code, 200)

    def test_profile_forbids_mass_assignment_and_password_changes(self):
        self.authenticate()
        for field in (
            "id",
            "user",
            "customer",
            "is_staff",
            "is_superuser",
            "is_active",
            "groups",
            "user_permissions",
            "role",
            "password",
            "status",
            "total",
        ):
            with self.subTest(field=field):
                response = self.client.patch("/api/auth/me/", {field: self.other.pk}, format="json")
                self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff or self.user.is_superuser)
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_profile_duplicate_email_and_invalid_fields_leave_all_fields_unchanged(self):
        self.authenticate()
        for data in (
            {"email": "OUTRO@EXAMPLE.COM", "name": "Nao Salvar"},
            {"name": ""},
            {"name": None},
            {"phone": "0" * 21},
        ):
            with self.subTest(data=data):
                response = self.client.patch("/api/auth/me/", data, format="json")
                self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Cliente Ficticio")
        self.assertEqual(self.user.email, "cliente@example.com")

    def test_profile_phone_save_failure_rolls_back_name(self):
        with patch("accounts.services.Customer.save", side_effect=RuntimeError("falha controlada")):
            with self.assertRaises(RuntimeError):
                update_profile(user=self.user, name="Nao Salvar", phone="11")
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Cliente Ficticio")

    def test_admin_can_use_profile_without_customer_but_cannot_create_customer_via_phone(self):
        self.authenticate(self.admin)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "administrator")
        self.assertIsNone(response.data["phone"])
        response = self.client.patch("/api/auth/me/", {"name": "Admin Novo"}, format="json")
        self.assertEqual(response.status_code, 200)
        response = self.client.patch(
            "/api/auth/me/", {"name": "Nao Salvar", "phone": "11"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.name, "Admin Novo")
        self.assertFalse(Customer.objects.filter(user=self.admin).exists())

    def test_refresh_issues_access_without_extending_original_refresh(self):
        refresh = RefreshToken.for_user(self.user)
        before = dict(refresh.payload)
        response = self.refresh(refresh)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data), {"access"})
        self.assertEqual(AccessToken(response.data["access"])["user_id"], str(self.user.pk))
        self.assertEqual(refresh.payload, before)
        self.assertEqual(self.refresh(refresh).status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_public_endpoints_ignore_stale_authorization_header(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalido")
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.refresh(RefreshToken.for_user(self.user)).status_code, 200)
        self.assertEqual(self.register().status_code, 201)

    def test_refresh_rejects_inactive_deleted_user_and_changed_password(self):
        refresh = RefreshToken.for_user(self.user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.refresh(refresh).status_code, 401)
        User.objects.filter(pk=self.user.pk).update(is_active=True)
        self.user.set_password("Nova-Senha-719!")
        self.user.save(update_fields=["password"])
        self.assertEqual(self.refresh(refresh).status_code, 401)
        ghost = User.objects.create_user("removido@example.com", PASSWORD, name="Removido")
        removed_refresh = RefreshToken.for_user(ghost)
        ghost.delete()
        self.assertEqual(self.refresh(removed_refresh).status_code, 401)

    def test_access_rejects_inactive_deleted_user_and_changed_password(self):
        self.authenticate()
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        User.objects.filter(pk=self.user.pk).update(is_active=True)
        self.user.set_password("Nova-Senha-719!")
        self.user.save(update_fields=["password"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        ghost = User.objects.create_user("removido@example.com", PASSWORD, name="Removido")
        self.authenticate(ghost)
        ghost.delete()
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_invalid_expired_tampered_and_wrong_kind_tokens_are_rejected(self):
        access = AccessToken.for_user(self.user)
        refresh = RefreshToken.for_user(self.user)
        expired_access, expired_refresh = (
            AccessToken.for_user(self.user),
            RefreshToken.for_user(self.user),
        )
        expired_access.set_exp(lifetime=timedelta(seconds=-1))
        expired_refresh.set_exp(lifetime=timedelta(seconds=-1))
        access_text, refresh_text = str(access), str(refresh)
        for access_value, refresh_value in (
            ("invalid", "invalid"),
            (str(expired_access), str(expired_refresh)),
            (str(refresh), str(access)),
            (access_text[:-8] + "AAAAAAAA", refresh_text[:-8] + "AAAAAAAA"),
            (
                jwt.encode(access.payload, "", algorithm="none"),
                jwt.encode(refresh.payload, "", algorithm="none"),
            ),
            (
                jwt.encode(access.payload, "different-key-" * 8, algorithm="HS256"),
                jwt.encode(refresh.payload, "different-key-" * 8, algorithm="HS256"),
            ),
        ):
            with self.subTest(kind=access_value[:15]):
                self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_value}")
                self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
                self.assertEqual(self.refresh(refresh_value).status_code, 401)

    def test_malformed_user_claim_never_causes_internal_error(self):
        for claim in (None, "abc", "9" * 20, [], {}, True, "-1", "0", "１"):
            with self.subTest(claim=claim):
                access, refresh = AccessToken.for_user(self.user), RefreshToken.for_user(self.user)
                access["user_id"], refresh["user_id"] = claim, claim
                self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
                self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
                self.assertEqual(self.refresh(refresh).status_code, 401)

    def test_wrong_audience_or_issuer_is_rejected(self):
        for key in ("aud", "iss"):
            access, refresh = AccessToken.for_user(self.user), RefreshToken.for_user(self.user)
            # TokenBackend define aud/iss ao serializar: assinar payload explicitamente.
            for token, endpoint in ((access, "access"), (refresh, "refresh")):
                payload = dict(token.payload, aud="loja-api", iss="loja-portfolio-local")
                payload[key] = "outro-projeto"
                signed = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
                if endpoint == "access":
                    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {signed}")
                    self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
                else:
                    self.assertEqual(self.refresh(signed).status_code, 401)

    def test_json_only_safe_methods_and_no_production_probe_routes(self):
        response = self.client.post(
            "/api/auth/token/", "email=x", content_type="application/x-www-form-urlencoded"
        )
        self.assertEqual(response.status_code, 415)
        response = self.client.post(
            "/api/auth/token/", "{bad json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/auth/token/").status_code, 405)
        self.authenticate()
        self.assertEqual(self.client.put("/api/auth/me/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete("/api/auth/me/").status_code, 405)
        self.assertEqual(self.client.get("/_test/orders/").status_code, 404)

    def test_registration_throttle_limits_attempts_and_returns_retry_after(self):
        for attempt in range(5):
            self.assertEqual(
                self.client.post(
                    "/api/auth/register/",
                    {},
                    format="json",
                    HTTP_X_FORWARDED_FOR=f"192.0.2.{attempt + 1}",
                ).status_code,
                400,
            )
        response = self.client.post(
            "/api/auth/register/", {}, format="json", HTTP_X_FORWARDED_FOR="192.0.2.200"
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    def test_profile_service_also_validates_password_and_model_fields(self):
        with self.assertRaises(ValidationError):
            register_customer(email="service@example.com", name="Teste", password="123")
        with self.assertRaises(ValidationError):
            update_profile(user=self.user, name=" ")
