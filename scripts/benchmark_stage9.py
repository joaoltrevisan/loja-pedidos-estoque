"""Cria, mede e remove somente um banco novo, sem carregar a demonstracao."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write_result(output, result):
    # O teste inicial do pai nao basta: outro processo pode concluir antes do filho.
    # O_EXCL, usado pelo modo x, preserva a primeira evidencia mesmo nessa corrida.
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, default=str) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=int, default=20000)
    parser.add_argument("--customers", type=int, default=500)
    parser.add_argument("--products", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()
    from django.core.management import call_command
    from django.db import connection, connections

    from benchmarks.dataset import require_isolated_database, validate_sizes

    validate_sizes(args.orders, args.customers, args.products, args.seed)
    if not 3 <= args.repeats <= 30:
        parser.error("Use de 3 a 30 repeticoes.")
    if args.child:
        from benchmarks.runner import run_benchmark

        expected = os.environ.get("LOJA_BENCHMARK_DATABASE", "")
        require_isolated_database(expected)
        call_command("migrate", interactive=False, verbosity=0)
        result = run_benchmark(
            database=expected,
            orders=args.orders,
            customers=args.customers,
            products=args.products,
            seed=args.seed,
            repeats=args.repeats,
        )
        write_result(args.output, result)
        connections.close_all()
        return
    output = args.output.resolve()
    if output.exists():
        parser.error("A saida ja existe; escolha outro arquivo para preservar a evidencia.")
    output.parent.mkdir(parents=True, exist_ok=True)
    name = "loja_bench_" + uuid4().hex
    # Credenciais ficam nos parametros da conexao e no ambiente do filho, nunca nos logs.
    params = connection.get_connection_params()
    connections.close_all()
    with psycopg.connect(**params, autocommit=True) as controller:
        controller.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            env = {**os.environ, "PGDATABASE": name, "LOJA_BENCHMARK_DATABASE": name}
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--child",
                "--orders",
                str(args.orders),
                "--customers",
                str(args.customers),
                "--products",
                str(args.products),
                "--seed",
                str(args.seed),
                "--repeats",
                str(args.repeats),
                "--output",
                str(output),
            ]
            subprocess.run(command, env=env, cwd=ROOT, check=True)
        finally:
            # Sem FORCE, sem varrer bancos por prefixo e sem apagar a base de origem.
            controller.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    print(
        "Benchmark concluido; banco descartavel removido. Pagamentos SIMULADOS, sem cobranca real."
    )


if __name__ == "__main__":
    main()
