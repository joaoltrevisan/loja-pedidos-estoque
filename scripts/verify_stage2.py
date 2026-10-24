"""Executa verificacoes da Etapa 2 e preserva a saida real para revisao."""

import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import django
import psycopg

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "stage2-last-verification.txt"
sys.path.insert(0, str(ROOT))


def main():
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="config.settings.test")
    if not env.get("PGHOST"):
        socket_file = ROOT / ".local" / "socket-path"
        if not socket_file.exists():
            raise SystemExit("Configure PGHOST ou inicie o banco com scripts/local_postgres.py.")
        env.update(PGHOST=socket_file.read_text(), PGPORT="55432", PGUSER="loja", PGDATABASE="loja")

    os.environ.update(env)
    django.setup()
    from django.db import connection

    REPORT.parent.mkdir(exist_ok=True)
    with REPORT.open("w") as report:

        def emit(message):
            print(message, flush=True)
            report.write(message + "\n")
            report.flush()

        emit(f"Verificacao Etapa 2 — {datetime.now(UTC).isoformat()}")
        emit(
            f"Python {platform.python_version()}; Django {django.get_version()}; "
            f"psycopg {psycopg.__version__}"
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT version(), current_user, current_setting('TimeZone')")
            emit(f"Banco real: {cursor.fetchone()}")
            cursor.execute("SHOW listen_addresses")
            emit(f"listen_addresses: {cursor.fetchone()[0]!r}")

        commands = [
            [sys.executable, "-m", "pip", "--disable-pip-version-check", "--no-cache-dir", "check"],
            [str(ROOT / ".venv/bin/ruff"), "check", "."],
            [str(ROOT / ".venv/bin/ruff"), "format", "--check", "."],
            [sys.executable, "manage.py", "check"],
            [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
            [sys.executable, "manage.py", "migrate", "--noinput"],
            [sys.executable, "manage.py", "migrate", "--check"],
            [sys.executable, "manage.py", "test", "tests", "--noinput", "--verbosity", "2"],
        ]
        for command in commands:
            emit("\n$ " + " ".join(command))
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            emit(result.stdout.rstrip())
            emit(f"exit_code={result.returncode}")
            if result.returncode:
                raise SystemExit(result.returncode)
        emit("\nTodas as verificacoes acima terminaram com exit_code=0.")
    connection.close()
    print(f"Evidencia salva em {REPORT}")


if __name__ == "__main__":
    main()
