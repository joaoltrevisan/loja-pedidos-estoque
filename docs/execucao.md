# Executar a loja localmente

Este guia usa dados fictícios e **pagamentos simulados, sem cobrança real**. Não há serviço público hospedado. O ambiente é de desenvolvimento, com aplicação em loopback e PostgreSQL sem porta publicada no computador.

## Primeira execução

Pré-requisitos: Git, Docker Engine em execução com Compose e Python 3. O roteiro de apresentação usa também Bash, Python 3.9+ com dados de fuso horário e curl 7.82+. As versões da aplicação estão fixadas em `requirements.lock` e no Dockerfile.

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

A sonda deve retornar `{"status":"ok"}`. Abra o [Swagger local](http://127.0.0.1:8000/api/docs/) para navegar pelo contrato. Ele usa arquivos locais, sem CDN, e não persiste a autorização no navegador.

`create_env.py` gera quatro segredos locais distintos, preserva `.env.example`, cria `.env` com permissão restrita e recusa sobrescrever uma configuração existente. Se `.env` já existir, comece por `docker compose config --quiet`. Não execute `source .env`, não publique seu conteúdo e não use `docker compose config` sem `--quiet` em um registro público: a versão expandida pode revelar valores.

Se o computador não tiver Python, gere a configuração usando a imagem oficial:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" -w /workspace \
  python:3.12.15-slim-bookworm python scripts/create_env.py
```

A aplicação não cria administrador pelo cadastro público. O administrador fictício é criado por `seed_demo`; a senha local está em `DEMO_PASSWORD` no `.env`. O comando de demonstração exige `ENABLE_DEMO_DATA=true`, já preparado pelo gerador de configuração. Em uma configuração manual, preserve as demais variáveis e habilite esse campo somente no ambiente de demonstração.

## Dados iniciais conhecidos

`seed_demo` exige base de domínio vazia. Ele **não apaga registros, não pode ser repetido para resetar a base e não corrige dados existentes**.

| Entidade | Conjunto inicial |
| --- | --- |
| Usuários | `admin.demo@example.com` e `cliente1.demo@example.com` a `cliente3.demo@example.com` |
| Produtos | Caderno `25.90`, caneca `39.90`, caneta `4.50` |
| Pedidos | 5, um em cada estado |
| Pagamentos | 3 simulados |
| Saldos disponíveis | Caderno 26, caneca 17, caneta 45 |
| Faturamento de janeiro de 2026 | `168.10`, com 3 pagamentos; ticket `56.03` |

Os eventos iniciais estão em janeiro de 2026. Consultar outro período pode retornar zero; isso não indica falha no gerador. O [roteiro HTTP](demonstracao.md) cria registros novos com datas do momento da execução.

## Retomar, atualizar e parar

Depois da preparação inicial:

```bash
docker compose up -d --wait
docker compose ps
```

Depois de mudar o código ou atualizar a cópia local:

```bash
docker compose build app
docker compose run --rm app migrate --noinput
docker compose up -d --wait app
```

Para parar preservando os dados:

```bash
docker compose down
```

Não use `down --volumes` na base que deseja manter. Para outra demonstração limpa, escolha **outro nome de projeto Compose**, em vez de apagar o volume existente.

## Ambiente isolado para apresentar o projeto

Escolha um nome novo e uma porta livre. Execute todos os comandos com o mesmo nome/porta. Se repetir, use outro nome: o gerador não sobrescreve a base anterior.

```bash
APP_PORT=18011 docker compose -p loja-apresentacao-01 config --quiet
APP_PORT=18011 docker compose -p loja-apresentacao-01 build app
APP_PORT=18011 docker compose -p loja-apresentacao-01 up -d --wait db
APP_PORT=18011 docker compose -p loja-apresentacao-01 run --rm app migrate --noinput
APP_PORT=18011 docker compose -p loja-apresentacao-01 run --rm app seed_demo
APP_PORT=18011 docker compose -p loja-apresentacao-01 up -d --wait app
bash examples/demonstracao.sh http://127.0.0.1:18011
```

Essa execução reutiliza a configuração privada local, mas cria rede, containers e volume diferentes. A porta da aplicação continua restrita a loopback. Ao terminar, pare preservando os dados com:

```bash
APP_PORT=18011 docker compose -p loja-apresentacao-01 down
```

O script HTTP cria um cliente e dois produtos exclusivos por execução, além de dois pedidos. Não é um reset nem uma transação única de todas as chamadas. Evite executá-lo na base que quer conservar exatamente igual.

## Ambiente já preparado neste desenvolvimento

A demonstração anterior usa o projeto `loja-stage3-20261023223148` e a porta `18003`, com seus dados preservados. Para consultar ou retomar esse ambiente:

```bash
APP_PORT=18003 docker compose -p loja-stage3-20261023223148 ps
APP_PORT=18003 docker compose -p loja-stage3-20261023223148 up -d --wait
```

Sua sonda é [127.0.0.1:18003/health/](http://127.0.0.1:18003/health/). Não execute o gerador novamente nesse volume. O ensaio final da Etapa 11 usa outro nome/volume/porta e confere o hash do domínio principal antes e depois.

## Verificar

```bash
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test app test tests --noinput --verbosity 2
docker compose run --rm --entrypoint ruff app check .
docker compose run --rm --entrypoint ruff app format --check .
bash -n examples/demonstracao.sh
python3 scripts/check_publication.py
```

A suíte tem 251 testes, incluindo concorrência com conexões PostgreSQL independentes. A CI executa também dependências, checks Django, migrations, comparação do OpenAPI exportado e scanner. Veja a [matriz de riscos](etapa-10-testes-ci.md). O [guia de validação local sem Docker](etapa-02-validacao.md) descreve a alternativa com ambiente virtual; ela exige PostgreSQL real.

## Se algo falhar

- Docker indisponível: inicie o Engine/Desktop e confira `docker info`.
- Porta ocupada: escolha outra `APP_PORT` e use a mesma porta no endereço do roteiro.
- Configuração incompleta: confira os nomes de variáveis em `.env.example`, sem copiar segredos para logs.
- `seed_demo` recusa a base: preserve o volume e use outro projeto para uma demonstração limpa.
- Login falha: use o administrador fictício e a senha do `.env` que preparou **aquele volume**. Mudar o arquivo depois não altera a senha já gravada no banco.
- Código antigo no container: reconstrua a imagem e recrie a aplicação.
- Roteiro interrompido: as chamadas já confirmadas continuam no banco. Ele não repete automaticamente operações POST; investigue a resposta em um ambiente local privado ou use outra demonstração limpa.
