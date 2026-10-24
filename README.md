# Loja: pedidos e estoque

Projeto pessoal para desenvolvimento back-end e modelagem de banco de dados.

Código público: [joaoltrevisan/loja-pedidos-estoque](https://github.com/joaoltrevisan/loja-pedidos-estoque). O [registro de publicação](docs/publicacao-github.md) explica o que foi enviado e as verificações de privacidade. A aplicação é executada localmente; não há deploy público.

## Entrega atual

**Etapa 9: índices e medições implementados, verificados e aprovados em revisão técnica.**

Leia [a definição do domínio](docs/etapa-01-dominio.md): regras, permissões, transições, relacionamentos, decisões de integridade, exemplos e critérios de verificação.

Leia também a [modelagem detalhada](docs/etapa-02-modelagem.md), o [parecer aprovado da Etapa 2](docs/etapa-02-parecer.md), o [ambiente da Etapa 3](docs/etapa-03-ambiente.md) e seu [pacote de revisão](docs/etapa-03-revisao.md).

Já existem modelos Django, quatro migrations iniciais, testes para PostgreSQL, Dockerfile, Compose, gerador de demonstração e autenticação JWT. A [Etapa 4](docs/etapa-04-autenticacao.md) explica cadastro, login, renovação e perfil próprio; seu [pacote de revisão](docs/etapa-04-revisao.md) registra os arquivos e verificações, e o [parecer](docs/etapa-04-parecer.md) registra a aprovação e a correção encontrada.

A [Etapa 5](docs/etapa-05-pedidos.md) acrescenta `POST /api/orders/`: o servidor define dono, preço, total e estado, reserva o estoque e registra os movimentos na mesma transação. O [pacote de revisão](docs/etapa-05-revisao.md) lista arquivos, decisões, testes e limites; o [parecer final](docs/etapa-05-parecer.md) aprova a entrega sem bloqueadores.

A [Etapa 6](docs/etapa-06-transicoes.md) acrescenta pagamento simulado, cancelamento, envio e entrega, com repetições protegidas e conferência de histórico. Seu [pacote de revisão](docs/etapa-06-revisao.md) registra arquivos, decisões e verificações; o [parecer final](docs/etapa-06-parecer.md) aprova a entrega sem bloqueadores. A Etapa 7 acrescenta consulta/listagem, catálogo, gestão de estoque e documentação.

## Tecnologias previstas

- Python, Django e Django REST Framework.
- PostgreSQL, inclusive nos testes de integração e concorrência.
- JWT com biblioteca mantida e compatível com o Django escolhido.
- OpenAPI e Swagger UI.
- Docker Compose para aplicação e banco.
- GitHub Actions para as verificações automatizadas.

Versões usadas: Python 3.12.15, Django 5.2.18 LTS, DRF 3.18.3, SimpleJWT 5.5.1, PyJWT 2.15.1, PostgreSQL 17.11, psycopg 3.3.6 e Ruff 0.17.2. Fontes oficiais e dependências transitivas estão registradas na documentação de validação e em `requirements.lock`. OpenAPI usa drf-spectacular 0.30.0 e Swagger UI local com drf-spectacular-sidecar 2026.10.1; a combinação foi verificada nesta entrega.

Código e identificadores serão escritos em inglês; explicações e documentação, em português.

## Desenvolvimento incremental

| Etapa | Entrega | Situação |
| --- | --- | --- |
| 1 | Domínio e fluxos | Documentada; revisão de consistência registrada |
| 2 | Diagrama detalhado, modelos, migrations e restrições | Aprovada em revisão; 27 testes repetidos com êxito |
| 3 | Ambiente reproduzível e dados fictícios | Concluída e aprovada; 41 testes em container com PostgreSQL |
| 4 | Autenticação e permissões | Aprovada no escopo definido; 79 testes; integração nos futuros endpoints pendente |
| 5 | Criação transacional de pedidos | Aprovada; 109 testes locais e Docker; compra e rollback verificados |
| 6 | Pagamento simulado, cancelamento e entrega | Aprovada em revisão; 152 testes locais e 152 no Docker |
| 7 | API e documentação OpenAPI | Aprovada no escopo operacional; relatórios acrescentados na Etapa 8 |
| 8 | Consultas de negócio | Aprovada em revisão; 228 testes locais e 228 no Docker |
| 9 | Índices e medições de desempenho | Aprovada com correção da revisão; 248 testes locais e 248 no Docker |
| 10 | Cobertura dos riscos e integração contínua | Planejada; testes pertinentes começam nas etapas anteriores |
| 11 | Material de portfólio e demonstração | Planejada |

Apenas o ambiente mínimo de validação com PostgreSQL foi antecipado na Etapa 2. A partir dela, cada entrega termina com arquivos, decisões, resultados reais e revisão técnica; a próxima etapa só começa após a revisão. A consulta de pedidos agora verifica o acesso do dono nas rotas reais. A [Etapa 7](docs/etapa-07-api.md) explica a API, os erros padronizados, as decisões e a dependência dos relatórios com a Etapa 8. O [pacote de revisão](docs/etapa-07-revisao.md) lista arquivos e evidências; o [parecer final](docs/etapa-07-parecer.md) registra a aprovação e a correção de paginação. A [Etapa 8](docs/etapa-08-relatorios.md) entrega as consultas e os endpoints de relatórios. O [pacote de revisão](docs/etapa-08-revisao.md) registra arquivos, critérios, testes e limites. A [Etapa 9](docs/etapa-09-desempenho.md) avalia sete consultas com 20 mil pedidos fictícios em banco separado, mantém dois índices justificados e registra casos sem ganho. Seu [pacote de revisão](docs/etapa-09-revisao.md) lista arquivos e verificações, e o [parecer final](docs/etapa-09-parecer.md) registra a aprovação e a correção da saída concorrente. A Etapa 10 não foi iniciada.

## Executar com Docker Compose

Pré-requisito: Docker Engine em execução e `docker compose` disponível (por exemplo, Docker Desktop). O roteiro abaixo foi executado em projeto e volume novos, com Docker Desktop 4.96.3, Engine 29.9.2 e Compose 5.6.1.

Para obter o código pela primeira vez:

```bash
git clone https://github.com/joaoltrevisan/loja-pedidos-estoque.git
cd loja-pedidos-estoque
```

Na pasta do projeto, gere uma configuração local. O script usa somente a biblioteca padrão do Python 3, não exibe os segredos e não sobrescreve um `.env` existente. Se o arquivo já estiver preparado, preserve-o e comece pelo comando `docker compose config --quiet`:

```bash
python3 scripts/create_env.py
docker compose config --quiet
docker compose build app
docker compose up -d --wait db
docker compose run --rm app migrate --noinput
docker compose run --rm app seed_demo
docker compose up -d --wait app
curl --fail http://127.0.0.1:8000/health/
```

O resultado esperado da sonda é `{"status":"ok"}`. Ela comprova acesso ao banco, sem expor dados ou credenciais. O banco não publica uma porta no computador; a aplicação atende somente em `127.0.0.1`. Esta é uma configuração de desenvolvimento local.

Se não houver Python no computador, a alternativa para gerar `.env` é:

```bash
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/workspace" -w /workspace python:3.12.15-slim-bookworm python scripts/create_env.py
```

O gerador cria **3 clientes fictícios, 3 produtos e 5 pedidos**, um por estado. Os **3 pagamentos são simulados, sem cobrança real**. Execute `seed_demo` uma única vez: ele exige uma base de domínio vazia, recusa repetições e não apaga dados. Os emails são `admin.demo@example.com` e `cliente1.demo@example.com` a `cliente3.demo@example.com`; a senha local está em `DEMO_PASSWORD`, no `.env`. O login agora está disponível em `POST /api/auth/token/`.

Para iniciar novamente depois da primeira preparação, use `docker compose up -d --wait`. Para parar, use `docker compose down`; o volume de dados é preservado. Mudanças no código exigem reconstruir a imagem com `docker compose build app` e recriar a aplicação com `docker compose up -d --wait app`.

Verificações pelo container:

```bash
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test app test tests --noinput --verbosity 2
docker compose run --rm --entrypoint ruff app check .
docker compose run --rm --entrypoint ruff app format --check .
```

Esses comandos passaram dentro do container. Consulte as [evidências da execução Docker](docs/etapa-03-docker-evidencias.txt), as [verificações locais anteriores](docs/etapa-03-evidencias.txt) e as [decisões do ambiente](docs/etapa-03-ambiente.md).

O ambiente de verificação deste computador usa o projeto `loja-stage3-20261023223148` e a porta `18003`, mantendo o volume separado do projeto padrão. A sonda está em [127.0.0.1:18003/health/](http://127.0.0.1:18003/health/). Para administrar esse ambiente já preparado:

```bash
APP_PORT=18003 docker compose -p loja-stage3-20261023223148 ps
APP_PORT=18003 docker compose -p loja-stage3-20261023223148 down
APP_PORT=18003 docker compose -p loja-stage3-20261023223148 up -d --wait
```

Não execute `seed_demo` novamente nesse volume: o comando recusará a base preenchida. `down` preserva os dados; a persistência foi conferida recriando os containers e comparando o conteúdo.

## Rotas disponíveis

| Operação | Rota |
| --- | --- |
| Cadastrar cliente | `POST /api/auth/register/` |
| Fazer login | `POST /api/auth/token/` |
| Renovar acesso | `POST /api/auth/token/refresh/` |
| Consultar perfil próprio | `GET /api/auth/me/` |
| Atualizar nome, email ou telefone próprios | `PATCH /api/auth/me/` |
| Listar produtos ativos (cliente) ou todos (admin) | `GET /api/products/` |
| Criar produto (admin) | `POST /api/products/` |
| Consultar / atualizar ou inativar produto | `GET /api/products/{id}/`, `PATCH` (admin) |
| Consultar estoque (admin) | `GET /api/stock/`, `GET /api/stock/{product_id}/` |
| Registrar entrada ou ajuste (admin) | `POST /api/stock/{product_id}/movements/` |
| Auditar movimentos (admin) | `GET /api/stock/movements/` |
| Listar ou consultar pedidos visíveis | `GET /api/orders/`, `GET /api/orders/{id}/` |
| Criar pedido e reservar estoque | `POST /api/orders/` |
| Faturamento diário/mensal e ticket médio simulados (admin) | `GET /api/reports/revenue/`, `GET /api/reports/average-ticket/` |
| Produtos e clientes com mais vendas simuladas (admin) | `GET /api/reports/top-products/`, `GET /api/reports/top-customers/` |
| Estoque baixo (admin) | `GET /api/reports/low-stock/` |
| Pedidos por status e pendências antigas (admin) | `GET /api/reports/orders-by-status/`, `GET /api/reports/oldest-pending/` |
| Abrir Swagger UI / baixar contrato | `GET /api/docs/`, `GET /api/schema/` |
| Confirmar pagamento simulado (admin) | `POST /api/orders/{id}/simulated-payment/` |
| Cancelar pendente (cliente dono) | `POST /api/orders/{id}/cancel/` |
| Enviar pedido pago (admin) | `POST /api/orders/{id}/ship/` |
| Registrar entrega (admin) | `POST /api/orders/{id}/deliver/` |

Envie objetos JSON. Use `Authorization: Bearer <access>` para consultar ou atualizar o perfil. O login recebe `email` e `password`; a renovação recebe `refresh`. A documentação da [Etapa 4](docs/etapa-04-autenticacao.md) contém campos, limites, respostas e decisões de segurança. As respostas com tokens não devem ser compartilhadas. No ambiente deste computador, a base da URL é `http://127.0.0.1:18003`.

Criar pedido também exige token de cliente; informe somente `items` e `shipping_address`. Veja o [exemplo completo e as regras da Etapa 5](docs/etapa-05-pedidos.md). Com caderno a `25.90`, comprar três unidades calcula `77.70` no servidor e reduz três unidades disponíveis. Falha em qualquer gravação desfaz a criação inteira. Uma segunda compra concorrente espera o bloqueio e verifica o saldo atualizado. Repetir o POST cria outro pedido, sujeito ao estoque; não há chave de idempotência nem expiração automática de reservas nesta versão.

As ações usam corpo `{}`, exceto envio, que aceita `tracking_code` opcional. Pagamento usa o total histórico do pedido e nunca desconta estoque novamente. Cancelamento só devolve a reserva de um pendente do próprio cliente. Repetir ações válidas preserva registros e datas; repetir envio exige o mesmo código. Veja [contrato, fluxos e exemplos da Etapa 6](docs/etapa-06-transicoes.md).

Os relatórios financeiros usam pagamentos **simulados, sem cobrança real**, pela data de aprovação em `America/Sao_Paulo`. Não representam apuração contábil ou fiscal. Produtos vendidos usam o preço histórico; contagem por status usa criação do pedido. Consulte o [guia dos indicadores, filtros e exemplos](docs/etapa-08-relatorios.md).

A suíte atual tem **248 testes**, aprovados no PostgreSQL local e na imagem Docker Linux ARM64. Os [resultados reais](docs/etapa-09-evidencias.txt) incluem 20 testes novos do experimento e todas as verificações anteriores. Os tempos da suíte não são medidas de desempenho da aplicação. O [relatório de desempenho](docs/etapa-09-desempenho.md) separa planos e tempos SQL da contagem de consultas HTTP e registra seus limites.

Abra a documentação interativa em [Swagger UI local](http://127.0.0.1:18003/api/docs/) no ambiente já preparado, ou use a porta `8000` na configuração padrão. O [OpenAPI exportado](docs/openapi.yaml) permite explorar o contrato sem executar a aplicação. Os exemplos são fictícios; tokens gerados localmente não devem ser publicados.

## Verificar localmente

Com o ambiente virtual e o PostgreSQL local já preparados:

```bash
cd loja-pedidos-estoque
.venv/bin/python scripts/local_postgres.py start
.venv/bin/python scripts/verify_stage2.py
.venv/bin/python scripts/local_postgres.py stop
```

Para preparar a validação em outro ambiente ou usar um PostgreSQL existente, siga as [instruções completas](docs/etapa-02-validacao.md). A chave pública da configuração `test` é exclusiva de testes. A configuração `development` exige `DJANGO_SECRET_KEY` definido no ambiente.

Não há deploy público da aplicação. Antes de enviar, execute `python3 scripts/check_publication.py`: `.env`, dados/bancos locais e ambientes virtuais ficam fora do Git. Caminhos pessoais das evidências históricas foram anonimizados, preservando os resultados dos testes. Os commits usam email `noreply` do GitHub.
