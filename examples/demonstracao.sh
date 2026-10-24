#!/usr/bin/env bash
# Dados ficticios e pagamentos SIMULADOS. Execute em uma demonstracao separada.
set +x
set -euo pipefail
umask 077

demo_base=$(python3 -I - "${1:-http://127.0.0.1:8000}" <<'PY'
import sys
from urllib.parse import urlsplit

try:
    url = urlsplit(sys.argv[1])
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username is not None or url.password is not None
            or url.path not in {"", "/"} or url.query or url.fragment
            or (url.port is not None and not 1 <= url.port <= 65535)):
        raise ValueError("Origem nao permitida")
except ValueError:
    raise SystemExit("Use somente a origem HTTP local, sem usuario, caminho ou parametros.")
print(sys.argv[1].rstrip("/"))
PY
)
demo_env_file=${DEMO_ENV_FILE:-.env}
demo_tmp=$(mktemp -d)
trap 'rm -rf -- "$demo_tmp"' EXIT

# Nao executar .env como codigo, nem colocar senhas nos argumentos de processos.
python3 -I - "$demo_env_file" "$demo_tmp" <<'PY'
import json
import secrets
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

config = dict(line.split("=", 1) for line in Path(sys.argv[1]).read_text().splitlines()
              if line and not line.startswith("#") and "=" in line)
password = config.get("DEMO_PASSWORD", "")
if not password:
    raise SystemExit("Preencha DEMO_PASSWORD no arquivo local criado por scripts/create_env.py.")
folder = Path(sys.argv[2])
tag = uuid4().hex[:12]
customer = {"email": f"roteiro.{tag}@example.com", "name": "Cliente Ficticio do Roteiro",
            "password": secrets.token_urlsafe(24) + "Aa9!"}
payloads = {
    "register": customer,
    "customer-login": {key: customer[key] for key in ("email", "password")},
    "admin-login": {"email": "admin.demo@example.com", "password": password},
    "product": {"sku": f"ROTEIRO-{tag.upper()}", "name": "Caderno Ficticio do Roteiro",
                "price": "25.90"},
    "empty-product": {"sku": f"VAZIO-{tag.upper()}", "name": "Produto Ficticio Sem Estoque",
                      "price": "10.00"},
    "entry": {"movement_type": "ENTRY", "quantity_delta": 5,
              "reason": "Entrada ficticia do roteiro de portfolio."},
    "empty": {},
    "ship": {"tracking_code": f"SIMULATED-{tag.upper()}"},
    "started": {"date": datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()},
}
for name, data in payloads.items():
    (folder / f"{name}-body.json").write_text(json.dumps(data))
PY

json_value() {
    python3 -I -c 'import json,sys; value=json.load(open(sys.argv[1])); print(value[sys.argv[2]])' "$@"
}

make_header() {
    python3 -I - "$demo_tmp/$1.json" "$demo_tmp/$2.headers" <<'PY'
import json
import sys
from pathlib import Path

token = json.loads(Path(sys.argv[1]).read_text())["access"]
if not isinstance(token, str) or "\r" in token or "\n" in token:
    raise SystemExit("Token de acesso invalido.")
Path(sys.argv[2]).write_text("Authorization: Bearer " + token + "\n")
PY
}

call_api() {
    local demo_name=$1 demo_method=$2 demo_path=$3 demo_expected=$4
    local demo_auth=${5:--} demo_body=${6:--} demo_status
    local demo_args=(--request "$demo_method")
    if [ "$demo_auth" != "-" ]; then
        demo_args+=(--header "@$demo_tmp/$demo_auth.headers")
    fi
    if [ "$demo_body" != "-" ]; then
        demo_args+=(--json "@$demo_tmp/$demo_body-body.json")
    fi
    demo_status=$(curl --disable --silent --show-error --proto '=http' --noproxy '*' \
        --connect-timeout 3 --max-time 15 \
        --output "$demo_tmp/$demo_name.json" --write-out '%{http_code}' \
        "${demo_args[@]}" "$demo_base$demo_path")
    printf '%s: HTTP %s (esperado %s)\n' "$demo_name" "$demo_status" "$demo_expected"
    if [ "$demo_status" != "$demo_expected" ]; then
        printf 'Roteiro interrompido; resposta privada nao sera exibida.\n' >&2
        exit 1
    fi
}

printf 'DEMONSTRACAO FICTICIA — pagamentos SIMULADOS, SEM COBRANCA REAL.\n'
call_api health GET /health/ 200
call_api admin-login POST /api/auth/token/ 200 - admin-login
make_header admin-login admin
call_api admin-profile GET /api/auth/me/ 200 admin
python3 -I - "$demo_tmp/admin-profile.json" <<'PYROLE'
import json
import sys

if json.load(open(sys.argv[1]))["role"] != "administrator":
    raise SystemExit("Use o administrador ficticio criado por seed_demo.")
PYROLE
call_api register POST /api/auth/register/ 201 - register
call_api customer-login POST /api/auth/token/ 200 - customer-login
make_header customer-login customer
call_api product POST /api/products/ 201 admin product
demo_product_id=$(json_value "$demo_tmp/product.json" id)
call_api empty-product POST /api/products/ 201 admin empty-product
demo_empty_id=$(json_value "$demo_tmp/empty-product.json" id)
call_api entry POST "/api/stock/$demo_product_id/movements/" 201 admin entry
call_api products GET /api/products/ 200 customer
call_api stock-before GET "/api/stock/$demo_product_id/" 200 admin

python3 -I - "$demo_tmp" "$demo_product_id" "$demo_empty_id" <<'PY'
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
address = {"recipient": "Cliente Ficticio", "street": "Rua Imaginaria", "number": "123",
           "district": "Bairro Modelo", "city": "Sao Paulo", "state": "SP", "postal_code": "01001000"}
for name, product, quantity in (("order", sys.argv[2], 3), ("cancel-order", sys.argv[2], 2),
                                ("no-stock", sys.argv[3], 1)):
    payload = {"items": [{"product_id": int(product), "quantity": quantity}],
               "shipping_address": address}
    (folder / f"{name}-body.json").write_text(json.dumps(payload))
PY

call_api order POST /api/orders/ 201 customer order
demo_order_id=$(json_value "$demo_tmp/order.json" id)
call_api stock-reserved GET "/api/stock/$demo_product_id/" 200 admin
call_api payment POST "/api/orders/$demo_order_id/simulated-payment/" 200 admin empty
call_api ship POST "/api/orders/$demo_order_id/ship/" 200 admin ship
call_api deliver POST "/api/orders/$demo_order_id/deliver/" 200 admin empty
call_api stock-delivered GET "/api/stock/$demo_product_id/" 200 admin
call_api cancel-order POST /api/orders/ 201 customer cancel-order
demo_cancel_id=$(json_value "$demo_tmp/cancel-order.json" id)
call_api stock-cancel-reserved GET "/api/stock/$demo_product_id/" 200 admin
call_api cancel POST "/api/orders/$demo_cancel_id/cancel/" 200 customer empty
call_api stock-restored GET "/api/stock/$demo_product_id/" 200 admin
call_api empty-stock GET "/api/stock/$demo_empty_id/" 200 admin
call_api no-stock POST /api/orders/ 409 customer no-stock

demo_period=$(python3 -I - "$demo_tmp/started-body.json" <<'PY'
import json
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

start = date.fromisoformat(json.load(open(sys.argv[1]))["date"])
end = datetime.now(ZoneInfo("America/Sao_Paulo")).date() + timedelta(days=1)
print(f"start={start.isoformat()}&end={end.isoformat()}")
PY
)
call_api revenue GET "/api/reports/revenue/?$demo_period" 200 admin
call_api ticket GET "/api/reports/average-ticket/?$demo_period" 200 admin

python3 -I - "$demo_tmp" <<'PY'
import json
import sys
from decimal import Decimal
from pathlib import Path

folder = Path(sys.argv[1])
def load(name):
    return json.loads((folder / f"{name}.json").read_text())
balances = [load(name)["available_quantity"] for name in
            ("stock-before", "stock-reserved", "stock-delivered", "stock-cancel-reserved", "stock-restored")]
assert balances == [5, 2, 2, 0, 2]
assert load("order")["total"] == "77.70"
assert load("payment")["simulated_payment"]["is_simulated"] is True
assert load("payment")["simulated_payment"]["amount"] == "77.70"
assert load("deliver")["order"]["status"] == "DELIVERED"
assert load("cancel")["order"]["status"] == "CANCELLED"
assert load("empty-stock")["available_quantity"] == 0
assert load("no-stock")["code"] == "insufficient_stock"
assert load("revenue")["payment_mode"] == "SIMULATED_NO_REAL_CHARGE"
assert Decimal(load("revenue")["total"]) >= Decimal("77.70")
assert load("ticket")["paid_orders"] == load("revenue")["paid_orders"]
print("Saldos conferidos: 5 -> 2 -> 2 -> 0 -> 2; produto sem estoque: 0.")
print("Pedido entregue: 77.70 BRL; segundo pedido cancelado; pagamento SIMULADO.")
print("Faturamento global do periodo:", load("revenue")["total"], "BRL; ticket:", load("ticket")["average_ticket"])
print("A soma global pode incluir outros pedidos. O roteiro cria registros novos a cada execucao.")
PY
printf 'Melhoria medida: consulte docs/etapa-09-desempenho.md; este roteiro nao mede latencia.\n'
printf 'Roteiro concluido; arquivos temporarios privados serao removidos.\n'
