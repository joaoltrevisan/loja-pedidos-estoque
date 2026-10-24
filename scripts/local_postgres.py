"""PostgreSQL descartavel da Etapa 2: socket privado, sem TCP ou servico do sistema."""

import argparse
import subprocess
import tempfile
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
BIN = LOCAL / "postgresql" / "bin"
DATA = LOCAL / "pgdata"
SOCKET_FILE = LOCAL / "socket-path"
PORT = "55432"


def run(binary, *arguments, check=True):
    return subprocess.run([str(BIN / binary), *arguments], check=check)


def start():
    if not (BIN / "initdb").exists():
        raise SystemExit("PostgreSQL local ausente. Consulte docs/etapa-02-validacao.md.")
    if not DATA.exists():
        run(
            "initdb",
            "-D",
            str(DATA),
            "-U",
            "stage2_bootstrap",
            "--auth-local=trust",
            "--auth-host=reject",
            "--encoding=UTF8",
            "--locale=C",
        )
    if run("pg_ctl", "-D", str(DATA), "status", check=False).returncode == 0:
        print("PostgreSQL local ja esta em execucao.")
        socket = Path(SOCKET_FILE.read_text())
    else:
        # mkdtemp usa permissao 0700; trust fica restrito ao dono deste diretorio.
        socket = Path(tempfile.mkdtemp(prefix="loja-pg-", dir="/private/tmp"))
        SOCKET_FILE.write_text(str(socket))
        run(
            "pg_ctl",
            "-D",
            str(DATA),
            "-l",
            str(LOCAL / "postgres-server.log"),
            "-o",
            f"-k {socket} -h '' -p {PORT} -c timezone=UTC",
            "-w",
            "start",
        )
    with psycopg.connect(
        host=str(socket), port=PORT, dbname="postgres", user="stage2_bootstrap", autocommit=True
    ) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'loja'").fetchone():
            # CREATEDB serve apenas ao runner de testes; nunca e uma role de producao.
            conn.execute("CREATE ROLE loja LOGIN CREATEDB NOSUPERUSER NOCREATEROLE")
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = 'loja'").fetchone():
            conn.execute("CREATE DATABASE loja OWNER loja")
    print(f"PGHOST={socket}\nPGPORT={PORT}\nPGUSER=loja\nPGDATABASE=loja")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    action = parser.parse_args().action
    if action == "start":
        start()
    elif action == "stop":
        run("pg_ctl", "-D", str(DATA), "-m", "fast", "-w", "stop")
    else:
        run("pg_ctl", "-D", str(DATA), "status")
