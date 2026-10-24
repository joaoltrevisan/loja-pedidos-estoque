"""Contrato OpenAPI: apresentacao/documentacao, sem regras de negocio."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_field,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from accounts.serializers import (
    ActiveUserRefreshSerializer,
    LoginSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    RegistrationSerializer,
)
from accounts.views import LoginView, ProfileView, RefreshView, RegistrationView
from catalog.serializers import ProductInputSerializer, ProductQuerySerializer, ProductSerializer
from catalog.views import ProductDetailView, ProductListView
from inventory.serializers import (
    MovementQuerySerializer,
    StockChangeResultSerializer,
    StockChangeSerializer,
    StockMovementSerializer,
    StockQuerySerializer,
    StockSerializer,
)
from inventory.views import StockChangeView, StockDetailView, StockListView, StockMovementListView
from orders.serializers import (
    EmptyActionSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderQuerySerializer,
    OrderSerializer,
    OrderTransitionSerializer,
    ShippingActionSerializer,
)
from orders.views import (
    OrderCancelView,
    OrderCreateView,
    OrderDeliverView,
    OrderDetailView,
    OrderShipView,
    SimulatedPaymentView,
)


class StoreJWTScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.DatabaseJWTAuthentication"
    name = "jwtAuth"
    priority = 1

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


ERROR = inline_serializer(
    name="ApiError",
    fields={
        "code": serializers.CharField(),
        "detail": serializers.CharField(),
        "errors": serializers.JSONField(allow_null=True),
    },
)
ERROR_EXAMPLES = [
    OpenApiExample(
        "Erro de validacao",
        value={
            "code": "validation_error",
            "detail": "Revise os campos informados.",
            "errors": {"quantity_delta": ["Informe um inteiro JSON."]},
        },
        response_only=True,
        status_codes=["400"],
    ),
    OpenApiExample(
        "Conflito de estado",
        value={"code": "invalid_transition", "detail": "Transicao nao permitida.", "errors": None},
        response_only=True,
        status_codes=["409"],
    ),
]


def operation(
    summary,
    role,
    *,
    response,
    request=None,
    success=200,
    parameters=None,
    examples=None,
    description="",
    auth=None,
):
    errors = {
        code: OpenApiResponse(ERROR, text)
        for code, text in {
            400: "Entrada ou parametros invalidos; errors identifica campos.",
            401: "Token ausente, expirado ou invalido.",
            403: "Perfil sem permissao para a operacao.",
            404: "Registro inexistente ou fora da visibilidade do usuario; pagina inexistente.",
            405: "Metodo nao permitido.",
            409: "Conflito de estado, saldo, SKU ou integridade; nenhuma alteracao parcial.",
            415: "API aceita apenas application/json no corpo.",
            429: "Limite de requisicoes atingido; veja Retry-After.",
        }.items()
    }
    sample = success_example(response)
    examples = list(examples or [])
    if sample is not None and not any(e.response_only for e in examples):
        examples.append(
            OpenApiExample(
                "Resposta ilustrativa",
                value=sample,
                response_only=True,
                status_codes=[str(success)],
            )
        )
    kwargs = {
        "summary": summary,
        "description": f"Perfil autorizado: {role}. {description}",
        "request": request,
        "responses": {success: response, **errors},
        "examples": [*ERROR_EXAMPLES, *(examples or [])],
    }
    if parameters is not None:
        kwargs["parameters"] = [parameters]
    if auth is not None:
        kwargs["auth"] = auth
    return extend_schema(**kwargs)


PRODUCT = {
    "sku": "DEMO-PEN-001",
    "name": "Caneta Ficticia",
    "price": "5.90",
    "description": "Produto de demonstracao.",
    "is_active": True,
}
ADDRESS = {
    "recipient": "Cliente Ficticio",
    "street": "Rua Imaginaria",
    "number": "123",
    "district": "Bairro Modelo",
    "city": "Sao Paulo",
    "state": "SP",
    "postal_code": "01001000",
}
ORDER_INPUT = {"items": [{"product_id": 1, "quantity": 2}], "shipping_address": ADDRESS}
ORDER_EXAMPLE = {
    "id": 1,
    "customer_id": 1,
    "status": "PENDING_PAYMENT",
    "currency": "BRL",
    "total": "11.80",
    "shipping_address": {**ADDRESS, "complement": "", "country": "BR"},
    "items": [
        {
            "product_id": 1,
            "product_sku": "DEMO-PEN-001",
            "product_name": "Caneta Ficticia",
            "quantity": 2,
            "unit_price": "5.90",
            "subtotal": "11.80",
        }
    ],
    "created_at": "2026-01-15T10:00:00-03:00",
    "updated_at": "2026-01-15T10:00:00-03:00",
    "paid_at": None,
    "cancelled_at": None,
    "shipped_at": None,
    "delivered_at": None,
    "payment_mode": "SIMULATED_NO_REAL_CHARGE",
}


def success_example(response):
    child = getattr(response, "child", response)
    name = child.__class__.__name__ if not isinstance(child, type) else child.__name__
    when = "2026-01-15T10:00:00-03:00"
    profile = {
        "id": 1,
        "email": "cliente@example.com",
        "name": "Cliente Ficticio",
        "phone": "11900000000",
        "role": "customer",
    }
    product = {"id": 1, **PRODUCT, "available_quantity": 0, "created_at": when, "updated_at": when}
    stock = {"product_id": 1, "sku": PRODUCT["sku"], "available_quantity": 20, "updated_at": when}
    movement = {
        "id": 1,
        "product_id": 1,
        "order_id": None,
        "performed_by_id": 2,
        "movement_type": "ENTRY",
        "quantity_delta": 20,
        "created_at": when,
        "reason": "Abastecimento ficticio.",
    }
    examples = {
        "ProfileSerializer": profile,
        "TokenPair": {"access": "ACCESS_GERADO_LOCALMENTE", "refresh": "REFRESH_GERADO_LOCALMENTE"},
        "AccessToken": {"access": "ACCESS_GERADO_LOCALMENTE"},
        "ProductSerializer": product,
        "StockSerializer": stock,
        "StockMovementSerializer": movement,
        "StockChangeResultSerializer": {"stock": stock, "movement": movement},
        "OrderSerializer": ORDER_EXAMPLE,
        "OrderDetailSerializer": {**ORDER_EXAMPLE, "simulated_payment": None, "shipment": None},
    }
    sample = examples.get(name)
    return sample


def transition_example(view):
    order = dict(ORDER_EXAMPLE)
    payment = None
    shipment = None
    if view is OrderCancelView:
        order.update(
            status="CANCELLED",
            cancelled_at="2026-01-15T11:00:00-03:00",
            updated_at="2026-01-15T11:00:00-03:00",
        )
    else:
        paid = "2026-01-15T11:00:00-03:00"
        order.update(status="PAID", paid_at=paid, updated_at=paid)
        payment = {
            "id": 1,
            "amount": "11.80",
            "reference": "11111111-1111-4111-8111-111111111111",
            "approved_at": paid,
            "is_simulated": True,
        }
        if view in (OrderShipView, OrderDeliverView):
            shipped = "2026-01-15T12:00:00-03:00"
            order.update(status="SHIPPED", shipped_at=shipped, updated_at=shipped)
            shipment = {
                "id": 1,
                "tracking_code": "SIMULATED-001",
                "shipped_at": shipped,
                "delivered_at": None,
            }
        if view is OrderDeliverView:
            delivered = "2026-01-16T12:00:00-03:00"
            order.update(status="DELIVERED", delivered_at=delivered, updated_at=delivered)
            shipment["delivered_at"] = delivered
    return {"order": order, "simulated_payment": payment, "shipment": shipment}


def request_example(name, value):
    return OpenApiExample(name, value=value, request_only=True)


def configure_schema():
    extend_schema_field(OrderItemSerializer(many=True))(OrderSerializer.get_items)
    extend_schema_field(
        {
            "type": "object",
            "properties": {key: {"type": "string"} for key in (*ADDRESS, "complement", "country")},
        }
    )(OrderSerializer.get_shipping_address)
    extend_schema_field({"type": "string", "enum": ["SIMULATED_NO_REAL_CHARGE"]})(
        OrderSerializer.get_payment_mode
    )
    extend_schema_field({"type": "string", "nullable": True})(ProfileSerializer.get_phone)
    extend_schema_field({"type": "string", "enum": ["administrator", "customer", "unassigned"]})(
        ProfileSerializer.get_role
    )
    token_pair = inline_serializer(
        name="TokenPair",
        fields={"access": serializers.CharField(), "refresh": serializers.CharField()},
    )
    access = inline_serializer(name="AccessToken", fields={"access": serializers.CharField()})
    extend_schema_view(
        post=operation(
            "Cadastrar cliente",
            "publico",
            request=RegistrationSerializer,
            response=ProfileSerializer,
            success=201,
            auth=[],
            description="Nao aceita privilegios administrativos. Limite: 5/min por IP.",
            examples=[
                request_example(
                    "Cliente ficticio",
                    {
                        "email": "cliente@example.com",
                        "name": "Cliente Ficticio",
                        "password": "Exemplo-Ficticio-731!",
                        "phone": "11900000000",
                    },
                )
            ],
        )
    )(RegistrationView)
    extend_schema_view(
        post=operation(
            "Obter tokens JWT",
            "publico",
            request=LoginSerializer,
            response=token_pair,
            auth=[],
            description="Access dura 5 min; refresh dura 1 dia. Limite: 20/min por IP.",
            examples=[
                request_example(
                    "Login ficticio",
                    {"email": "cliente@example.com", "password": "Exemplo-Ficticio-731!"},
                )
            ],
        )
    )(LoginView)
    extend_schema_view(
        post=operation(
            "Renovar access token",
            "portador do refresh",
            request=ActiveUserRefreshSerializer,
            response=access,
            auth=[],
            description=(
                "Nao estende a validade do refresh. Usuario removido, inativo ou com senha "
                "alterada perde a renovacao. Limite: 60/min por IP."
            ),
            examples=[
                request_example("Substitua o refresh", {"refresh": "COLE_SEU_REFRESH_LOCAL"})
            ],
        )
    )(RefreshView)
    extend_schema_view(
        get=operation(
            "Consultar perfil proprio", "usuario autenticado", response=ProfileSerializer
        ),
        patch=operation(
            "Atualizar perfil proprio",
            "usuario autenticado",
            request=ProfileUpdateSerializer,
            response=ProfileSerializer,
            examples=[
                request_example(
                    "Contato ficticio", {"name": "Nome Ficticio", "phone": "11900000001"}
                )
            ],
        ),
    )(ProfileView)
    product_read = operation(
        "Listar produtos",
        "cliente ou administrador",
        response=ProductSerializer(many=True),
        parameters=ProductQuerySerializer,
        description=(
            "Clientes veem somente ativos; is_active e exclusivo do administrador. search "
            "busca nome/SKU; sku e exato. ordering: id, sku, name, price, created_at. Pagina "
            "padrao 20; page_size de 1 a 100. Parametros desconhecidos/repetidos sao "
            "rejeitados."
        ),
    )
    extend_schema_view(
        get=product_read,
        post=operation(
            "Criar produto com estoque zero",
            "administrador",
            request=ProductInputSerializer,
            response=ProductSerializer,
            success=201,
            examples=[request_example("Produto ficticio", PRODUCT)],
            description=(
                "Saldo inicial zero; abasteca pela rota de movimentos. Preco deve ser texto "
                "decimal positivo de ate duas casas; descricao ate 5000 caracteres."
            ),
        ),
    )(ProductListView)
    extend_schema_view(
        get=operation(
            "Consultar produto", "cliente (ativo) ou administrador", response=ProductSerializer
        ),
        patch=operation(
            "Atualizar ou inativar produto",
            "administrador",
            request=ProductInputSerializer,
            response=ProductSerializer,
            description=(
                "PATCH parcial. is_active=false preserva o historico; exclusao fisica nao e "
                "oferecida. Atualizacao bloqueia o produto para estabilizar compras concorrentes."
            ),
            examples=[
                request_example("Novo preco", {"price": "6.90"}),
                request_example("Inativacao", {"is_active": False}),
            ],
        ),
    )(ProductDetailView)
    extend_schema_view(
        get=operation(
            "Listar saldos",
            "administrador",
            response=StockSerializer(many=True),
            parameters=StockQuerySerializer,
            description=(
                "Filtros product_id e max_quantity (inclusivo). ordering: id, product_id, "
                "available_quantity, updated_at. Pagina padrao 20; maximo 100."
            ),
        )
    )(StockListView)
    extend_schema_view(
        get=operation("Consultar saldo de um produto", "administrador", response=StockSerializer)
    )(StockDetailView)
    extend_schema_view(
        get=operation(
            "Auditar movimentos de estoque",
            "administrador",
            response=StockMovementSerializer(many=True),
            parameters=MovementQuerySerializer,
            description=(
                "Filtros product_id, order_id e movement_type. ordering: id, created_at, "
                "product_id. Registros somente de leitura. Pagina padrao 20; maximo 100."
            ),
        )
    )(StockMovementListView)
    extend_schema_view(
        post=operation(
            "Registrar entrada ou ajuste",
            "administrador",
            request=StockChangeSerializer,
            response=StockChangeResultSerializer,
            success=201,
            description=(
                "ENTRY exige delta positivo; ADJUSTMENT admite positivo ou negativo, nunca zero. "
                "Justificativa obrigatoria ate 500 caracteres. Saldo final entre 0 e 2147483647. "
                "Movimento e saldo confirmam juntos. Repetir POST cria NOVO movimento; confira a "
                "auditoria antes de repetir apos falha de rede. Ajustar disponibilidade nao altera "
                "reservas existentes."
            ),
            examples=[
                request_example(
                    "Entrada ficticia",
                    {
                        "movement_type": "ENTRY",
                        "quantity_delta": 20,
                        "reason": "Abastecimento ficticio.",
                    },
                ),
                request_example(
                    "Ajuste ficticio",
                    {
                        "movement_type": "ADJUSTMENT",
                        "quantity_delta": -2,
                        "reason": "Correcao ficticia de contagem.",
                    },
                ),
            ],
        )
    )(StockChangeView)
    extend_schema_view(
        get=operation(
            "Listar pedidos visiveis",
            "cliente (proprios) ou administrador (todos)",
            response=OrderDetailSerializer(many=True),
            parameters=OrderQuerySerializer,
            description=(
                "status e exato; customer_id exclusivo de administradores. created_from inclusivo "
                "e created_before exclusivo (ISO 8601, fuso America/Sao_Paulo quando omitido). "
                "ordering: id, created_at, total, status. Pagina padrao 20; maximo 100."
            ),
        ),
        post=operation(
            "Criar pedido e reservar estoque",
            "cliente",
            request=OrderCreateSerializer,
            response=OrderSerializer,
            success=201,
            description=(
                "De 1 a 100 produtos distintos, quantity inteiro JSON de 1 a 9999. Dono, preco, "
                "total e status definidos no servidor. Endereco brasileiro copiado para o "
                "historico. Nenhum pagamento real. POST repetido cria outro pedido; sem expiracao "
                "automatica."
            ),
            examples=[
                request_example("Compra ficticia", ORDER_INPUT),
                OpenApiExample(
                    "Pedido pendente", value=ORDER_EXAMPLE, response_only=True, status_codes=["201"]
                ),
            ],
        ),
    )(OrderCreateView)
    extend_schema_view(
        get=operation(
            "Consultar pedido visivel",
            "cliente (proprio) ou administrador",
            response=OrderDetailSerializer,
            description=(
                "Pedido alheio e inexistente retornam o mesmo 404. Inclui pagamento SIMULADO e "
                "envio quando existentes."
            ),
        )
    )(OrderDetailView)
    for view, name, role, detail, input_class in [
        (
            SimulatedPaymentView,
            "Confirmar pagamento SIMULADO",
            "administrador",
            (
                "PENDING_PAYMENT -> PAID. SEM COBRANCA REAL. Valor vem do total historico; nenhum "
                "novo desconto de estoque. Repeticoes em PAID/SHIPPED/DELIVERED preservam "
                "referencia e data. CANCELLED retorna 409."
            ),
            EmptyActionSerializer,
        ),
        (
            OrderCancelView,
            "Cancelar pedido pendente proprio",
            "cliente dono",
            (
                "PENDING_PAYMENT -> CANCELLED. Devolve a reserva uma unica vez. Repeticao em "
                "CANCELLED preserva estado e saldo; pago retorna 409. Pedido alheio retorna 404."
            ),
            EmptyActionSerializer,
        ),
        (
            OrderShipView,
            "Registrar envio",
            "administrador",
            (
                "PAID -> SHIPPED. Codigo opcional ate 100 caracteres. Repetir em SHIPPED/DELIVERED "
                "exige o mesmo codigo normalizado (omitir equivale a vazio); divergencia retorna "
                "409. Mantem data original."
            ),
            ShippingActionSerializer,
        ),
        (
            OrderDeliverView,
            "Registrar entrega",
            "administrador",
            "SHIPPED -> DELIVERED. Repeticao preserva a data original. Nenhum efeito no estoque.",
            EmptyActionSerializer,
        ),
    ]:
        extend_schema_view(
            post=operation(
                name,
                role,
                request=input_class,
                response=OrderTransitionSerializer,
                description=detail
                + " Operacao atomica; conflito de historico retorna 409 sem reparo automatico.",
                examples=[
                    request_example(
                        "Acao", {"tracking_code": "SIMULATED-001"} if view is OrderShipView else {}
                    ),
                    OpenApiExample(
                        "Transicao ilustrativa",
                        value=transition_example(view),
                        response_only=True,
                        status_codes=["200"],
                    ),
                ],
            )
        )(view)
