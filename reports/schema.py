from drf_spectacular.utils import OpenApiExample, extend_schema_view

from . import serializers, views


def configure_report_schema():
    from common.schema import operation

    period = (
        "start e end obrigatorios em YYYY-MM-DD; periodo de 1 a 366 dias, inicio inclusivo "
        "e fim exclusivo, em America/Sao_Paulo. Somente pagamentos SIMULADOS de pedidos "
        "PAID, SHIPPED ou DELIVERED, pela aprovacao. Sem cobranca real ou apuracao fiscal. "
    )
    metadata = {
        "start": "2026-01-01",
        "end": "2026-01-03",
        "timezone": "America/Sao_Paulo",
        "currency": "BRL",
        "payment_mode": "SIMULATED_NO_REAL_CHARGE",
        "notice": "SIMULADO: sem cobranca real; nao e apuracao contabil ou fiscal.",
    }
    entries = [
        (
            views.RevenueView,
            serializers.RevenueQuerySerializer,
            serializers.RevenueReportSerializer,
            "Faturamento SIMULADO por dia ou mes",
            period
            + (
                "group_by=day (padrao) ou month. Preenche periodos sem pagamento com zero. Meses "
                "parciais somam somente o intervalo solicitado. Total e serie derivam do mesmo "
                "agregado SQL."
            ),
            {
                **metadata,
                "group_by": "day",
                "total": "107.70",
                "paid_orders": 2,
                "series": [
                    {"period_start": "2026-01-01", "amount": "77.70", "paid_orders": 1},
                    {"period_start": "2026-01-02", "amount": "30.00", "paid_orders": 1},
                ],
            },
        ),
        (
            views.AverageTicketView,
            serializers.PeriodQuerySerializer,
            serializers.AverageTicketSerializer,
            "Ticket medio SIMULADO",
            period
            + (
                "Soma dos pagamentos / numero de pagamentos, com arredondamento HALF_UP para duas "
                "casas. Conjunto vazio retorna 0.00 e contagem zero; itens nao multiplicam "
                "pagamentos."
            ),
            {**metadata, "total": "107.70", "paid_orders": 2, "average_ticket": "53.85"},
        ),
        (
            views.TopProductsView,
            serializers.ProductRankingQuerySerializer,
            serializers.ProductRankingSerializer(many=True),
            "Produtos mais vendidos",
            period
            + (
                "Soma unidades e quantidade * preco historico. Inclui produtos hoje inativos; "
                "SKU/nome da resposta sao os atuais, agrupando por product_id. ordering: "
                "product_id, units_sold, simulated_revenue; padrao -units_sold, desempate por "
                "product_id. Pagina padrao 20, page_size 1..100. Vazio retorna results=[]."
            ),
            {
                "product_id": 1,
                "sku": "REPORT-RENAMED",
                "name": "Nome atual ficticio",
                "units_sold": 4,
                "simulated_revenue": "107.50",
            },
        ),
        (
            views.TopCustomersView,
            serializers.CustomerRankingQuerySerializer,
            serializers.CustomerRankingSerializer(many=True),
            "Clientes com maior valor comprado SIMULADO",
            period
            + (
                "Soma pagamentos por customer_id; nome atual, sem email ou endereco. ordering: "
                "customer_id, paid_orders, simulated_revenue; padrao -simulated_revenue, desempate "
                "por customer_id. Pagina padrao 20, page_size 1..100. Vazio retorna results=[]."
            ),
            {
                "customer_id": 1,
                "name": "Cliente Ficticio",
                "paid_orders": 1,
                "simulated_revenue": "77.70",
            },
        ),
        (
            views.LowStockView,
            serializers.LowStockQuerySerializer,
            serializers.LowStockSerializer(many=True),
            "Produtos ativos com estoque baixo",
            (
                "threshold obrigatorio, inteiro textual 0..2147483647. Saldo atual menor ou igual "
                "ao limite, somente produtos ativos. ordering: product_id, available_quantity; "
                "padrao available_quantity, desempate por product_id. Pagina padrao 20, page_size "
                "1..100. Vazio retorna results=[]."
            ),
            {
                "product_id": 1,
                "sku": "REPORT-RENAMED",
                "name": "Nome atual ficticio",
                "available_quantity": 5,
            },
        ),
        (
            views.OrderStatusView,
            serializers.PeriodQuerySerializer,
            serializers.OrderStatusReportSerializer,
            "Pedidos por estado atual",
            (
                "start e end obrigatorios, intervalo inclusivo/exclusivo de 1..366 dias em "
                "America/Sao_Paulo. Filtra CRIACAO do pedido, nao aprovacao do pagamento. Inclui "
                "os cinco estados, com zero onde nao ha registros. Nao representa faturamento."
            ),
            {
                "start": "2026-01-01",
                "end": "2026-02-01",
                "timezone": "America/Sao_Paulo",
                "date_basis": "order_created_at",
                "total_orders": 4,
                "statuses": [
                    {"status": "PENDING_PAYMENT", "count": 1},
                    {"status": "PAID", "count": 1},
                    {"status": "SHIPPED", "count": 1},
                    {"status": "DELIVERED", "count": 0},
                    {"status": "CANCELLED", "count": 1},
                ],
            },
        ),
        (
            views.OldestPendingView,
            serializers.PendingQuerySerializer,
            serializers.PendingOrderSerializer(many=True),
            "Pedidos pendentes ha mais tempo",
            (
                "Somente PENDING_PAYMENT criados ate o instante da consulta. min_age_hours "
                "opcional, 0..87600 (padrao 0), idade minima inclusiva. ordering: id, created_at, "
                "total; padrao created_at, desempate por id. Pagina padrao 20, page_size 1..100. "
                "Nao expira nem cancela reservas. Vazio retorna results=[]."
            ),
            {
                "id": 5,
                "customer_id": 1,
                "created_at": "2026-01-03T10:00:00-03:00",
                "total": "29.80",
                "currency": "BRL",
            },
        ),
    ]
    for view, params, output, title, description, sample in entries:
        extend_schema_view(
            get=operation(
                title,
                "administrador",
                parameters=params,
                response=output,
                description=description
                + " Parametros desconhecidos/repetidos ou inteiros fora do formato sao rejeitados.",
                error_codes=(400, 401, 403, 404, 405),
                examples=[
                    OpenApiExample(
                        "Resposta ilustrativa",
                        value=sample,
                        response_only=True,
                        status_codes=["200"],
                    )
                ],
            )
        )(view)
