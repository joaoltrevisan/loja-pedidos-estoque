# Loja: pedidos e estoque

Projeto pessoal para desenvolvimento back-end e modelagem de banco de dados.

API de uma loja fictícia com reservas de estoque, pedidos, histórico de preços, entrega e relatórios. **Todos os pagamentos são simulados, sem cobrança real.** O código é público; a aplicação é executada localmente, sem deploy público.

Repositório: [joaoltrevisan/loja-pedidos-estoque](https://github.com/joaoltrevisan/loja-pedidos-estoque). Verificações: [GitHub Actions](https://github.com/joaoltrevisan/loja-pedidos-estoque/actions/workflows/ci.yml).

## Entrega atual

**As onze etapas do projeto foram concluídas e aprovadas em revisão técnica.** A aplicação tem 251 testes. O roteiro final foi executado desde um volume novo, com chamadas curl reais e auditoria das invariantes. Consulte o [parecer da entrega final](docs/etapa-11-parecer.md).

O sistema permite cadastrar/autenticar clientes, consultar catálogo, criar pedidos com reserva transacional, aprovar pagamentos simulados, cancelar pendentes e registrar envio/entrega. Administradores gerenciam estoque e consultam sete relatórios. Clientes acessam somente os próprios pedidos.

## Explorar o projeto

| Material | Conteúdo |
| --- | --- |
| [Guia de execução](docs/execucao.md) | Preparação, dados fictícios, atualização, persistência e ambiente isolado |
| [Modelo e arquitetura](docs/arquitetura.md) | Diagrama ER, estados, transações, bloqueios e garantias do banco/serviços |
| [API](docs/api.md) | Papéis, recursos, erros e navegação do contrato |
| [OpenAPI exportado](docs/openapi.yaml) | Contrato validado e comparado pela CI |
| [Roteiro de apresentação](docs/demonstracao.md) | Onze pontos da demonstração, resultados esperados e observados |
| [Exemplos executáveis com curl](examples/demonstracao.sh) | Fluxo completo, sem imprimir senhas ou tokens |
| [Relatório de desempenho](docs/etapa-09-desempenho.md) | Volume/distribuição, planos, custos e casos sem ganho |
| [Matriz de testes e CI](docs/etapa-10-testes-ci.md) | Correspondência entre os 15 riscos exigidos e testes concretos |
| [Limites e próximos passos](docs/limites-e-proximos-passos.md) | Escopo funcional, operação, segurança e evoluções propostas |
| [Revisão da entrega final](docs/etapa-11-revisao.md) | Arquivos, decisões e evidências da Etapa 11 |

## Tecnologias

Python 3.12.15, Django 5.2.18 LTS, Django REST Framework 3.18.3, PostgreSQL 17.11, psycopg 3.3.6, JWT com SimpleJWT 5.5.1/PyJWT 2.15.1. Docker Compose reproduz o ambiente; Ruff 0.17.2 verifica estilo; GitHub Actions executa a suíte com PostgreSQL e conta sem superusuário.

As dependências diretas e transitivas estão fixadas em `requirements.lock`. Código e identificadores estão em inglês; explicações e documentação, em português.

## Começar

Com Git, Python 3 e Docker Engine/Compose disponíveis:

```bash
git clone https://github.com/joaoltrevisan/loja-pedidos-estoque.git
cd loja-pedidos-estoque
python3 scripts/create_env.py
docker compose config --quiet
docker compose build app
docker compose up -d --wait db
docker compose run --rm app migrate --noinput
docker compose run --rm app seed_demo
docker compose up -d --wait app
curl --disable --fail --silent --show-error --noproxy '*' http://127.0.0.1:8000/health/
```

Se `.env` já existir, preserve-o e comece por `config --quiet`. O gerador cria segredos locais distintos, não os exibe e não sobrescreve configuração. Há uma alternativa sem Python no host no [guia completo](docs/execucao.md).

O conjunto inicial contém **3 clientes fictícios, 3 produtos e 5 pedidos**, um por estado, com **3 pagamentos simulados**. Os saldos são 26/17/45; janeiro de 2026 tem faturamento simulado `168.10` e ticket `56.03`. A senha do administrador fictício `admin.demo@example.com` está em `DEMO_PASSWORD` no `.env`. O cadastro público não cria administradores.

`seed_demo` só funciona em base de domínio vazia e não apaga dados existentes. Para parar preservando o volume, use `docker compose down`. Para retomar, `docker compose up -d --wait`. Consulte o guia antes de atualizar ou preparar outra base.

Abra [Swagger local](http://127.0.0.1:8000/api/docs/). No ambiente anterior deste desenvolvimento, a porta é `18003` e o projeto Compose é `loja-stage3-20261023223148`; seus dados foram preservados. O guia explica como administrá-lo sem misturar volumes.

## Demonstrar

Em uma base de apresentação preparada e separada, com Bash, curl 7.82+ e Python 3.9+:

```bash
bash examples/demonstracao.sh http://127.0.0.1:18011
```

O [roteiro](docs/demonstracao.md) cria registros próprios, entrega um pedido de `77.70`, cancela outro pendente, mostra uma rejeição por saldo zero e consulta faturamento. As 24 chamadas foram conferidas em ambiente novo, com saldos **5 → 2 → 2 → 0 → 2**. Senhas/tokens ficam em arquivos temporários privados; os pagamentos permanecem simulados.

A demonstração é sequencial. A evidência de concorrência está nos testes com conexões PostgreSQL independentes e bloqueios observados. A [arquitetura](docs/arquitetura.md) explica por que duas compras não podem reservar a mesma última unidade e por que pagamento/cancelamento não confirmam juntos.

## Verificar

```bash
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test app test tests --noinput --verbosity 2
docker compose run --rm --entrypoint ruff app check .
docker compose run --rm --entrypoint ruff app format --check .
bash -n examples/demonstracao.sh
python3 scripts/check_publication.py
```

Reconstrua a imagem após alterar código. Os **251 testes** passaram no PostgreSQL local/Docker na Etapa 10 e novamente no Docker da demonstração final. A [CI hospedada da entrega final](https://github.com/joaoltrevisan/loja-pedidos-estoque/actions/runs/40140693590) também passou com 251 testes, Bash, migrations, OpenAPI e scanner. Os registros finais da Etapa 11 ficam em seu [pacote de revisão](docs/etapa-11-revisao.md).

A CI verifica também dependências, Django, migrations, contrato OpenAPI e arquivos publicáveis. Os tempos da suíte não são medidas de desempenho da API.

## Uma melhoria medida

Com **20 mil pedidos fictícios**, a consulta das 20 pendências mais antigas passou de mediana **0,939 para 0,013 ms** após um índice parcial por criação/ID para pendentes. O faturamento de um dia passou de **0,576 para 0,037 ms** com índice na aprovação do pagamento. O faturamento anual não apresentou ganho demonstrável.

São tempos SQL locais, com cache aquecido e sete amostras por fase. Não representam latência de produção. O [relatório](docs/etapa-09-desempenho.md) preserva comandos, planos, distribuição, custos, limites e investigação de N+1.

## Histórico incremental

| Etapa | Entrega |
| --- | --- |
| [1](docs/etapa-01-dominio.md) | Regras, fluxos e domínio |
| [2](docs/etapa-02-modelagem.md) | Modelos, migrations, restrições e validação PostgreSQL |
| [3](docs/etapa-03-ambiente.md) | Docker e dados fictícios |
| [4](docs/etapa-04-autenticacao.md) | Autenticação e permissões |
| [5](docs/etapa-05-pedidos.md) | Criação transacional e reserva |
| [6](docs/etapa-06-transicoes.md) | Pagamento simulado, cancelamento, envio e entrega |
| [7](docs/etapa-07-api.md) | Consultas, catálogo, estoque e OpenAPI |
| [8](docs/etapa-08-relatorios.md) | Relatórios e períodos |
| [9](docs/etapa-09-desempenho.md) | Índices e medições reais |
| [10](docs/etapa-10-testes-ci.md) | Cobertura dos riscos e integração contínua |
| [11](docs/etapa-11-revisao.md) | Portfólio e demonstração; aprovada em revisão e CI |

Cada entrega preserva seus critérios, evidências e parecer. Documentos antigos descrevem o estado daquela etapa; os guias acima apresentam o estado atual. Não foram implementadas evoluções fora do escopo apenas por estarem na lista de próximos passos.

O [registro de publicação](docs/publicacao-github.md) descreve as verificações de privacidade. `.env`, bancos, tokens, ambientes virtuais e resultados privados ficam fora do Git; os commits usam email `noreply`. Não há deploy público da aplicação.
