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


Abra o [Swagger local](http://127.0.0.1:8000/api/docs/) depois de iniciar a aplicação. O guia explica como preservar volumes e evitar misturar ambientes.


## Demonstrar


Em uma base de apresentação preparada e separada, com Bash, curl 7.82+ e Python 3.9+:


```bash
bash examples/demonstracao.sh http://127.0.0.1:18011
```


O [roteiro](docs/demonstracao.md) cria registros próprios, entrega um pedido de `77.70`, cancela outro pendente, mostra uma rejeição por saldo zero e consulta faturamento. As 24 chamadas foram conferidas em ambiente novo, com saldos **5 → 2 → 2 → 0 → 2**. Senhas/tokens ficam em arquivos temporários privados; os pagamentos permanecem simulados.
