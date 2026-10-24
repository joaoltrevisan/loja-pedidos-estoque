import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from scripts.create_env import create_env


class EnvironmentFileTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.template = self.root / "example"
        self.template.write_text(
            "DJANGO_SECRET_KEY=\nPOSTGRES_PASSWORD=\nPGPASSWORD=\nDEMO_PASSWORD=\n"
        )
        self.destination = self.root / "local.env"

    def test_secrets_are_distinct_private_and_example_is_preserved(self):
        original = self.template.read_bytes()
        create_env(self.template, self.destination)
        values = [line.split("=", 1)[1] for line in self.destination.read_text().splitlines()]
        self.assertEqual(len(set(values)), 4)
        self.assertTrue(all(len(value) >= 48 for value in values))
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.template.read_bytes(), original)

    def test_existing_configuration_is_not_overwritten(self):
        self.destination.write_text("existing-configuration")
        with self.assertRaises(FileExistsError):
            create_env(self.template, self.destination)
        self.assertEqual(self.destination.read_text(), "existing-configuration")

    def test_invalid_template_does_not_create_partial_file(self):
        self.template.write_text("DJANGO_SECRET_KEY=\n")
        with self.assertRaises(ValueError):
            create_env(self.template, self.destination)
        self.assertFalse(self.destination.exists())
