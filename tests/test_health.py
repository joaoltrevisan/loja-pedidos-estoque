from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase


class HealthTests(TestCase):
    def test_health_checks_real_database(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_database_failure_returns_503_without_details(self):
        with patch(
            "config.views.connection.cursor", side_effect=DatabaseError("private-host-secret")
        ):
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn(b"private-host-secret", response.content)

    def test_probe_only_accepts_safe_methods(self):
        response = self.client.head("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.post("/health/").status_code, 405)
