import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from orders.demo_data import create_demo_dataset


class Command(BaseCommand):
    help = "Cria dados ficticios em base vazia. PAGAMENTOS SIMULADOS, SEM COBRANCA REAL."

    def handle(self, *args, **options):
        if not settings.ENABLE_DEMO_DATA:
            raise CommandError(
                "Geracao desabilitada. Defina ENABLE_DEMO_DATA=true em ambiente local."
            )
        password = os.environ.get("DEMO_PASSWORD", "")
        if len(password) < 16:
            raise CommandError("Defina DEMO_PASSWORD com pelo menos 16 caracteres.")
        create_demo_dataset(password)
        self.stdout.write(
            self.style.SUCCESS(
                "Dados FICTICIOS criados: 3 clientes, 3 produtos, 5 pedidos. "
                "3 PAGAMENTOS SIMULADOS — SEM COBRANCA REAL."
            )
        )
