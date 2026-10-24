# Usar a API

Contrato completo: [OpenAPI exportado](openapi.yaml). Com a aplicação executando, abra [Swagger](http://127.0.0.1:8000/api/docs/) ou baixe `/api/schema/`. O Swagger usa arquivos locais e não persiste a autorização. Os [exemplos executáveis com curl](../examples/demonstracao.sh) e o [roteiro comentado](demonstracao.md) percorrem os fluxos principais.

A versão `0.8.0` do contrato corresponde à última etapa que acrescentou rotas. As Etapas 9–11 não alteram esse contrato; seus números não são versões de API.

## Autenticação e papéis

Cadastro público cria somente cliente, com senha validada e hash Django. Administrador é uma conta preparada no ambiente, não um parâmetro aceito no cadastro. O login recebe JSON com `email` e `password`; o token de acesso vai em `Authorization: Bearer <access>`. Renovação recebe `refresh`. Não publique tokens nem respostas de login.

O acesso dura 5 minutos e o refresh 1 dia, sem rotação nesta versão. Usuário inativo, removido ou com senha alterada perde o uso dos tokens conforme as verificações implementadas. Papéis são conferidos no banco; um token antigo não conserva um papel administrativo removido. As [decisões de autenticação](etapa-04-autenticacao.md) registram o alcance e as limitações.

## Recursos principais

| Recurso | Operações e perfil |
| --- | --- |
| `/api/auth/register/`, `/api/auth/token/`, `/api/auth/token/refresh/` | Cadastro/login/renovação públicos, com limites por escopo |
| `/api/auth/me/` | GET/PATCH do próprio perfil autenticado |
| `/api/products/`, `/api/products/{id}/` | GET para cliente/admin; POST e PATCH administrativos; cliente vê ativos |
| `/api/stock/`, `/api/stock/{product_id}/` | Consulta administrativa |
| `/api/stock/{product_id}/movements/` | POST de entrada/ajuste administrativo com razão e quantidade |
| `/api/stock/movements/` | GET administrativo da auditoria |
| `/api/orders/`, `/api/orders/{id}/` | Cliente consulta os próprios; admin consulta todos; criação somente por cliente |
| `/api/orders/{id}/simulated-payment/` | POST administrativo de pagamento simulado, sem cobrança real |
| `/api/orders/{id}/cancel/` | POST de cancelamento de pendente pelo próprio cliente |
| `/api/orders/{id}/ship/`, `/api/orders/{id}/deliver/` | POST administrativo de envio/entrega |
| `/api/reports/*` | Sete relatórios de leitura, exclusivos de administrador |

Pedidos aceitam `items` e `shipping_address`; dono, preço e total são definidos pelo servidor. Ações aceitam `{}`, exceto envio, que também permite `tracking_code`. Valores monetários de resposta são textos decimais em BRL; quantidades são inteiros. Os [contratos de pedido](etapa-05-pedidos.md), [transições](etapa-06-transicoes.md), [catálogo/listas](etapa-07-api.md) e [relatórios](etapa-08-relatorios.md) trazem campos, filtros e exemplos detalhados.

## Erros e listas

| HTTP | Significado típico |
| --- | --- |
| 400 | Formato/campo/filtro inválido, campo protegido ou produto inexistente na criação |
| 401 | Ausência de credencial válida em rota protegida |
| 403 | Papel sem autorização |
| 404 | Recurso ausente ou pedido fora do escopo de leitura do cliente |
| 409 | Conflito de estoque, transição ou integridade |
| 429 | Limite de requisições do escopo atingido |

O envelope de erro usa `code`, `detail` e `errors`. Não depende de o usuário interpretar um traceback. Respostas da API usam `Cache-Control: no-store`. Campos desconhecidos e tentativas de atribuir preço, dono ou privilégio são rejeitados.

Listas usam `page` e `page_size`, com padrão 20 e máximo 100. Cada recurso admite somente filtros e ordenações explicitamente documentados. O desempate por identificador dá ordem determinística; isso não congela páginas enquanto outros registros mudam. Relatórios por período exigem `start` e `end` como `YYYY-MM-DD`, entre 1 e 366 dias, com fim exclusivo em São Paulo.

O sistema não inclui pagamento real, envio por transportadora ou autenticação de produção pronta para exposição pública. Veja [limites e próximos passos](limites-e-proximos-passos.md).
