# Etapa 3 — Ambiente reproduzível e dados fictícios

## Situação da entrega

**Etapa concluída e aprovada em revisão técnica.** Implementação e verificações locais e em Docker aprovadas. A pendência inicial de execução dos containers foi resolvida em 23/10/2026, após a preparação do Docker. O [parecer complementar](etapa-03-parecer.md) aprovou o fechamento. A Etapa 4 não foi iniciada.

A Etapa 2 recebeu [parecer técnico independente favorável](etapa-02-parecer.md) antes do início desta etapa. A sugestão opcional sobre ampliar limites monetários não foi incorporada, para preservar o escopo da nova entrega.

## Decisões do ambiente

| Arquivo | Responsabilidade |
| --- | --- |
| `Dockerfile` | Imagem de desenvolvimento com dependências fixadas, usuário de sistema sem root e execução do Django |
| `compose.yaml` | Aplicação e PostgreSQL, rede interna, volume persistente e sondas de saúde |
| `.env.example` | Nomes de variáveis e opções locais, sem segredos |
| `scripts/create_env.py` | Segredos locais distintos, arquivo `0600`, sem sobrescrever configuração existente |
| `.dockerignore` | Excluir `.env`, ambientes virtuais, instalações locais e caches da imagem |
| `docker/postgres/01-app-role.sql` | Role da aplicação sem superusuário e propriedade do banco no primeiro início |
| `config/settings/base.py` | PostgreSQL por variáveis, fuso e habilitação explícita do gerador |
| `config/settings/development.py` / `test.py` | Separação já existente; chave própria obrigatória no desenvolvimento e chave pública restrita a testes |
| `config/views.py` | Sonda operacional com consulta simples ao banco, sem detalhes de exceção |

As versões de Python, Django e PostgreSQL da Etapa 2 foram mantidas. Imagens escolhidas: `python:3.12.15-slim-bookworm` e `postgres:17.11-bookworm`, ambas conferidas entre as tags das imagens oficiais. Tags fixam versões, mas não tornam os bytes imutáveis; os digests efetivamente usados estão agora registrados nas evidências de build e inspeção.

Fontes primárias consultadas em 23/10/2026: [imagem Python](https://hub.docker.com/_/python), [imagem PostgreSQL](https://hub.docker.com/_/postgres), [Dockerfile](https://docs.docker.com/reference/dockerfile/), [serviços do Compose](https://docs.docker.com/reference/compose-file/services/), [ordem de inicialização](https://docs.docker.com/compose/how-tos/startup-order/) e [psql, incluindo `\getenv`](https://www.postgresql.org/docs/17/app-psql.html).

O Compose espera o banco ficar saudável antes da aplicação. A sonda do banco usa TCP em `127.0.0.1` dentro do container, para não confundir o servidor temporário de inicialização com o servidor definitivo. O banco não tem porta publicada no host. O healthcheck da aplicação consulta `/health/`, que executa `SELECT 1`, retorna 200 se houver acesso e 503 sem detalhes internos se houver falha. A sonda não comprova que todas as migrations foram aplicadas: o roteiro executa migrations explicitamente antes de iniciar a aplicação.

O usuário do container é `app`, UID 10001. O filesystem da aplicação é somente leitura, com `/tmp` temporário gravável. A imagem inclui Ruff para os comandos de verificação deste ambiente de desenvolvimento. Usa o servidor de desenvolvimento do Django; não é uma configuração de publicação ou deploy.

O PostgreSQL inicia com uma credencial administrativa separada da aplicação. O SQL lê variáveis do ambiente com `\getenv` e usa o escape do psql para identificadores e valores. A role da aplicação não tem superusuário nem criação de roles; `CREATEDB` é usado para criar o banco descartável dos testes neste ambiente local. Scripts em `/docker-entrypoint-initdb.d` só executam quando o volume começa vazio. Alterar `.env` depois não muda automaticamente as senhas de um cluster já inicializado.

## Dados fictícios e dependência das próximas etapas

A Etapa 3 pede pedidos em estados válidos antes dos serviços das etapas 5 e 6. Para não antecipar a API nem fingir que esses serviços existem, o gerador é um construtor de dataset fechado, em `orders/demo_data.py`, chamado pelo comando administrativo `seed_demo`.

Ele exige `ENABLE_DEMO_DATA=true`, senha local com pelo menos 16 caracteres e base de domínio vazia. Executa antes de iniciar a aplicação. Não oferece reset nem remoção de dados. Uma repetição é rejeitada sem modificar registros; em outra base vazia, os mesmos valores de negócio são gerados novamente.

`transaction.atomic()` engloba toda a geração. Um bloqueio consultivo do PostgreSQL serializa execuções do próprio comando; isso não substitui os bloqueios de estoque das futuras compras. Não há garantia de execução junto a outros escritores: a preparação pressupõe uma base exclusiva, antes da aplicação subir.

Datas de negócio, produtos, quantidades, clientes e referências são determinísticos. Identificadores técnicos podem variar conforme as sequências; os hashes de senha variam deliberadamente por causa do salt. O gerador preserva o snapshot dos itens, copia o endereço, calcula totais com `Decimal`, registra entradas e reservas, libera apenas o pedido cancelado e cria pagamento e entrega conforme o estado final. Esse caminho de demonstração deverá ser reavaliado quando os serviços de negócio existirem, para compartilhar as regras sem criar uma implementação paralela de compras reais.

| Estado | Itens | Total | Pagamento simulado | Entrega |
| --- | --- | --- | --- | --- |
| `PENDING_PAYMENT` | 3 cadernos | `77.70` | Ausente | Ausente |
| `PAID` | 2 canecas | `79.80` | Aprovado | Ausente |
| `SHIPPED` | 1 caderno e 2 canetas | `34.90` | Aprovado | Enviada |
| `DELIVERED` | 1 caneca e 3 canetas | `53.40` | Aprovado | Entregue |
| `CANCELLED` | 2 cadernos, com liberação da reserva | `51.80` | Ausente | Ausente |

Saldo inicial: caderno 30, caneca 20, caneta 50. Saldo final esperado e conferido: **26, 17 e 45**. São 7 itens, 11 movimentações, 3 pagamentos simulados que somam **168.10** e 2 entregas. O pagamento não desconta estoque outra vez. Os dados têm datas fixas em janeiro de 2026; o pedido pendente continuará antigo, coerentemente com a ausência de expiração automática.

## Verificações realizadas

A [saída real](etapa-03-evidencias.txt) registra:

- 41 testes aprovados no PostgreSQL 17.11, incluindo os 27 anteriores e 14 novos.
- Reconciliação de itens, totais, pagamentos, entregas, responsáveis, reservas/liberações e estoque do dataset.
- Reprodutibilidade em base vazia e recusa de repetição sem apagar ou duplicar dados.
- Rollback completo após falha controlada depois de uma entrada de estoque.
- Habilitação e senha exigidas para o gerador, hash das credenciais e privilégios apenas no administrador fictício.
- Criação segura do `.env`, preservação de arquivo existente e ausência de arquivo parcial quando o exemplo é inválido.
- Sonda saudável, falha do banco sem vazamento de detalhes e rejeição de métodos que alteram dados.
- Ruff aprovado, 48 arquivos formatados, checks do Django sem problemas, modelos/migrations sem divergência ou pendência.
- `config --quiet` aprovado no executável oficial Docker Compose 5.6.1, e rejeição de configuração sem os segredos exigidos. O executável foi baixado para `.local` e teve SHA-256 conferido; isso não instala um Engine.
- SQL de bootstrap executado em banco temporário no PostgreSQL real: role sem superusuário/creação de roles, senha SCRAM, `CREATEDB` de testes e propriedade do banco conferidos; banco e role temporários removidos depois.
- Comando `seed_demo` executado na base local e requisição HTTP real ao Django em `development`: `GET /health/` retornou `200` e `{"status":"ok"}`. O processo HTTP foi encerrado.

O verificador temporário de bootstrap precisou de uma correção na própria consulta de inspeção: o caractere `%` de um padrão `LIKE` deve ser passado como parâmetro quando se usa psycopg. O SQL de inicialização do projeto executou corretamente; a inspeção corrigida foi repetida e aprovada. Nenhum resultado de container ou de desempenho é inferido desses testes locais.

## Validacao real em Docker

Preparei o ambiente Docker para executar o projeto localmente. Foi instalado o Docker Desktop oficial 4.96.3 para Apple Silicon, com SHA-256 conferido: `a3ac78b7de67af169ca58f33a4fa4c26007840870574c80c59a7ab0c7f68d954`. A instalação por linha de comando encontrou uma configuração em `/Library` que exigia permissão administrativa; foi usada a instalação padrão copiando o aplicativo para `/Applications`. O cliente ficou no diretório do usuário e o contexto em `desktop-linux`, sem criar manualmente symlinks de sistema ou alterar `/etc/hosts`. O instalador foi desmontado após a instalação.

Fontes: [instalação oficial no macOS](https://docs.docker.com/desktop/setup/install/mac-install/), [requisitos de permissão](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/) e [release 4.96.3](https://docs.docker.com/desktop/release-notes/#4963). Versões efetivas: Docker Engine 29.9.2 e Compose 5.6.1.

O roteiro do [README](../README.md) foi executado com o nome de projeto `loja-stage3-20261023223148`, volume novo e porta `127.0.0.1:18003`, preservando a base PostgreSQL local anterior. As [evidências de Docker](etapa-03-docker-evidencias.txt) registram:

- Build real da imagem Linux ARM64 com todas as dependências instaladas.
- Inicialização do banco pelo entrypoint oficial, incluindo a role da aplicação e o script montado.
- Aplicação de todas as migrations em base vazia e geração do dataset fictício.
- Saúde de ambos os containers e requisição HTTP real com resposta `200` e `{"status":"ok"}`.
- **41 testes aprovados dentro do container**, usando PostgreSQL 17.11, sem substituir o banco por SQLite.
- Lint, formatação e consistência das migrations aprovados dentro do container.
- UID efetivo 10001, filesystem somente leitura, `/tmp` gravável e `.env` ausente da imagem.
- Role da aplicação sem superusuário nem criação de roles; `CREATEDB` de testes e fuso UTC conferidos pela conexão da aplicação.
- Totais e quantidades conhecidos conferidos na base do container; 3 pagamentos simulados somando `168.10`; estoques finais `26`, `17` e `45`.
- `down` seguido de `up -d --wait`, sem apagar o volume: snapshot dos dados idêntico e HTTP saudável.
- Segunda execução do seed recusada com código 1 esperado; snapshot posterior preservado, sem duplicações.

Dentro do container foram conferidos Python 3.12.15, Django 5.2.18, psycopg 3.3.6 e PostgreSQL 17.11 em Linux `aarch64`. Os tempos do runner são duração de testes, não medições de desempenho do sistema.

A primeira coleta de metadados tentou inspecionar a tag da imagem base Python no daemon. O BuildKit havia usado essa base sem registrar a tag como imagem independente, então a inspeção retornou 1. O build e as verificações funcionais já haviam passado. A coleta foi ajustada para as imagens efetivamente registradas; o digest da base está no `FROM` do log de build. Essa ocorrência está preservada na evidência, sem ser apresentada como um teste aprovado.

Para uma segunda execução sem apagar os dados existentes, escolher outro nome de projeto Compose e outra porta (`COMPOSE_PROJECT_NAME` e `APP_PORT`) em ambiente separado e seguir o mesmo roteiro. Não apagar volumes automaticamente para obter uma base vazia.

A aplicação, as imagens Linux, os mounts, o entrypoint oficial, as permissões e a rede entre containers foram verificados juntos. O parecer complementar aprovou a resolução da pendência e confirmou aplicação e banco saudáveis, além de repetir a requisição HTTP com sucesso. A validação cobre Linux ARM64 neste ambiente de desenvolvimento; outras arquiteturas, concorrência das futuras compras e desempenho não foram demonstrados. Não foi feita publicação de imagem, deploy externo ou envio ao GitHub.
