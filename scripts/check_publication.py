"""Inspecao local antes de publicar; nunca imprime valores encontrados."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def main():
    files = set(
        filter(
            None, git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
        )
    )
    private_values = [str(Path.home())]
    email = subprocess.run(
        ["git", "config", "--global", "--get", "user.email"], capture_output=True, text=True
    ).stdout.strip()
    if email and not email.endswith("@users.noreply.github.com"):
        private_values.append(email)
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if (
                    key in {"POSTGRES_PASSWORD", "PGPASSWORD", "DJANGO_SECRET_KEY", "DEMO_PASSWORD"}
                    and value
                ):
                    private_values.append(value)
    patterns = [
        re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"/(?:Users|home)/[^/\s]+"),
    ]
    failures = []
    for name in sorted(files):
        path = ROOT / name
        if path.is_symlink():
            failures.append((name, "link simbolico exige revisao"))
            continue
        if name.startswith((".env", ".local/", ".venv/")) and name != ".env.example":
            failures.append((name, "arquivo local nao publicavel"))
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            if name != "docs/etapa-07-swagger.png":
                failures.append((name, "binario exige revisao"))
            continue
        if any(value in text for value in private_values) or any(p.search(text) for p in patterns):
            failures.append((name, "possivel dado privado ou credencial"))
    if failures:
        for name, reason in failures:
            print(f"REVISAR {name}: {reason}; valor omitido.")
        raise SystemExit(1)
    print(
        f"OK: {len(files)} arquivos candidatos; nenhum segredo local, token, "
        "email pessoal configurado ou caminho de usuario encontrado."
    )
    print(
        "Escopo: conteudo atual do repositorio. A imagem do Swagger foi conferida "
        "visualmente; historico Git e configuracao remota exigem verificacao propria."
    )


if __name__ == "__main__":
    main()
