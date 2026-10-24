"""Gera segredos locais sem exibi-los nem sobrescrever configuracao existente."""

import os
import re
import secrets
from pathlib import Path


def create_env(template, destination):
    content = template.read_text()
    for key in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "PGPASSWORD", "DEMO_PASSWORD"):
        content, count = re.subn(rf"(?m)^{key}=$", f"{key}={secrets.token_urlsafe(48)}", content)
        if count != 1:
            raise ValueError(f"O exemplo deve conter exatamente uma linha vazia para {key}.")
    # O_EXCL torna a protecao contra sobrescrita atomica, inclusive entre dois processos.
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(content)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    try:
        create_env(root / ".env.example", root / ".env")
    except FileExistsError:
        raise SystemExit(".env ja existe; nenhuma configuracao foi sobrescrita.") from None
    print(".env criado com segredos locais distintos e permissao 0600. Valores nao exibidos.")
