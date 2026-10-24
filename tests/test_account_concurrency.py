from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings

from accounts.models import Customer, User
from accounts.services import register_customer, update_profile
from tests.test_authentication import PASSWORD, TEST_HASHERS


@override_settings(PASSWORD_HASHERS=TEST_HASHERS)
class AccountConcurrencyTests(TransactionTestCase):
    def test_concurrent_same_email_registration_commits_one_complete_customer(self):
        barrier = Barrier(2, timeout=10)
        original_save = User.save

        def synchronized_save(instance, *args, **kwargs):
            # Os dois full_clean ja passaram, mas nenhum INSERT ocorreu ainda.
            if instance._state.adding:
                barrier.wait()
            return original_save(instance, *args, **kwargs)

        def register():
            close_old_connections()
            try:
                register_customer(email="race@example.com", name="Ficticio", password=PASSWORD)
                return "created"
            except ValidationError as error:
                self.assertIn("email", error.message_dict)
                return "conflict"
            finally:
                connections.close_all()

        with (
            patch.object(User, "save", synchronized_save),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            results = list(pool.map(lambda _: register(), range(2)))
        self.assertCountEqual(results, ["created", "conflict"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.get().user.email, "race@example.com")

    def test_concurrent_profile_fields_are_preserved_with_independent_connections(self):
        user = register_customer(email="profile@example.com", name="Original", password=PASSWORD)
        barrier = Barrier(2, timeout=10)

        def update(fields):
            close_old_connections()
            try:
                barrier.wait()
                update_profile(user=user, **fields)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(update, ({"name": "Nome Novo"}, {"email": "novo@example.com"})))
        user.refresh_from_db()
        self.assertEqual(user.name, "Nome Novo")
        self.assertEqual(user.email, "novo@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff or user.is_superuser)
