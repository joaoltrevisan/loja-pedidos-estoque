# Etapa 2 — Versões, execução e evidências

## Seleção das versões

Fontes consultadas em 23/10/2026, antes da instalação das respectivas dependências. Optou-se pelo Django 5.2 LTS, com patch atual, em vez de uma série mais nova, para manter uma base de suporte prolongado compatível com o ecossistema necessário.

| Componente | Versão usada | Fonte e decisão |
| --- | --- | --- |
| Python | 3.12.15 | [Release oficial](https://www.python.org/downloads/release/python-31215/) e [matriz do Django](https://docs.djangoproject.com/en/5.2/faq/install/#what-python-version-can-i-use-with-django). O runtime existente 3.12.14 foi substituído apenas no projeto após a consulta indicar a atualização. |
| Django | 5.2.18 LTS | [Versões suportadas](https://www.djangoproject.com/download/#supported-versions); suporte estendido da série até abril de 2028. |
| PostgreSQL | 17.11 | [Política oficial](https://www.postgresql.org/support/versioning/), [fontes da versão](https://www.postgresql.org/ftp/source/v17.11/) e [requisitos do Django](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes). Série estável com suporte; não usar versão RC. |
| psycopg / psycopg-binary | 3.3.6 | [Instalação oficial](https://www.psycopg.org/psycopg3/docs/basic/install.html), [release no PyPI](https://pypi.org/project/psycopg/3.3.6/). Driver da série 3, com distribuição binária para o ambiente. |
| Ruff | 0.17.2 | [Documentação oficial](https://docs.astral.sh/ruff/) e [release no PyPI](https://pypi.org/project/ruff/0.17.2/); lint e formatação. |

Dependências transitivas instaladas: `asgiref==3.13.0`, `sqlparse==0.6.0`, `typing_extensions==4.16.0`. `requirements.txt` declara as dependências da aplicação; `requirements-dev.txt` adiciona Ruff; `requirements.lock` registra todas as versões efetivamente instaladas, sem hashes de distribuição. O lock atual é a fotografia do ambiente Python 3.12/macOS; a futura imagem Linux deverá ser verificada na Etapa 3.

DRF, JWT e OpenAPI ainda não estão instalados. Foram consultadas as [matrizes do DRF](https://www.django-rest-framework.org/#requirements), do [Simple JWT](https://pypi.org/project/djangorestframework-simplejwt/5.5.1/) e do [drf-spectacular](https://drf-spectacular.readthedocs.io/en/latest/readme.html#requirements). O Simple JWT 5.5.1 declara Django 5.2 nos metadados publicados, embora a página `stable/getting_started` ainda liste séries anteriores. Essa diferença impede usar só aquela página como matriz atual. A escolha final da combinação DRF/JWT será revalidada e testada na Etapa 4; OpenAPI, na Etapa 7. Não se presume compatibilidade apenas porque o instalador aceita uma combinação.

## Ambiente mínimo utilizado

O computador não tinha Docker nem PostgreSQL. Antecipou-se apenas a infraestrutura indispensável para verificar a Etapa 2; não foram criados Dockerfile, Compose, dados de demonstração ou CI.

- Python 3.12.15 instalado em `.local/python` com uv 0.13.5, sem alterar o Python do sistema ou o PATH. A [documentação do uv](https://docs.astral.sh/uv/guides/install-python/) explica que suas distribuições vêm de `python-build-standalone`, mantido pela Astral, e não são instaladores binários publicados pelo CPython.
- Ambiente virtual privado em `.venv`.
- PostgreSQL compilado das fontes oficiais em `.local/postgresql`.
- SHA-256 conferido com o arquivo oficial: `dd27f2b3c59e73ed14aa3324901242bf69a032a6347805f274e6260322d42979` para `postgresql-17.11.tar.bz2`.
- Cluster descartável em `.local/pgdata`; socket Unix em diretório temporário com permissão `0700`; TCP desativado e autenticação de host configurada como `reject`.
- Autenticação `trust` somente pelo socket privado, acessível ao usuário local dono do diretório. Não reutilizar essa configuração como configuração de produção.
- Role `loja` sem superusuário nem criação de roles, com `CREATEDB` exclusivamente para o runner criar/remover `test_loja`.
- Servidor e conexões Django em UTC; aplicação usa `America/Sao_Paulo` para apresentação.
- `.local`, `.venv`, caches e segredos estão excluídos pelo `.gitignore`.

A build local não inclui ICU, readline, zlib ou TLS. Essas opções reduzem dependências apenas para a validação por socket privado e não representam a configuração do futuro container. Não houve medição de desempenho.

## Repetir a validação

### Usando PostgreSQL já instalado

Requisitos: Python 3.12.15 e PostgreSQL 17.11 disponíveis. Crie um banco exclusivo de desenvolvimento e uma role local com permissão de criação de banco de teste. Não aponte para dados reais ou compartilhados.

```bash
cd loja-pedidos-estoque
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
export PGHOST=127.0.0.1
export PGPORT=5432
export PGDATABASE=loja
export PGUSER=loja
# Defina PGPASSWORD no ambiente, se o seu banco exigir senha.
.venv/bin/python scripts/verify_stage2.py
```

O verificador usa `config.settings.test`, identifica o banco real, executa os comandos abaixo e interrompe na primeira falha. O teste falha se a role for superusuário ou se o backend não for PostgreSQL. As verificações não aceitam SQLite como substituto.

### Usando a instalação isolada deste computador

```bash
.venv/bin/python scripts/local_postgres.py start
.venv/bin/python scripts/verify_stage2.py
.venv/bin/python scripts/local_postgres.py stop
```

O verificador lê o socket registrado em `.local/socket-path` quando `PGHOST` não foi informado. Variáveis explícitas permitem usar outro PostgreSQL. Na validação local, iniciar o servidor e conectar ao socket exigiram permissão de execução; isso não é uma dependência adicional do Django.

Para reconstruir a instalação local do PostgreSQL no macOS com Command Line Tools, baixe e confira as fontes oficiais acima, extraia em `.local` e execute a partir de `.local/postgresql-17.11`:

```bash
./configure --prefix="$PWD/.local/postgresql" --without-icu --without-readline --without-zlib
make -j4
make install
```

Essa preparação temporária será substituída pelo ambiente completo da Etapa 3. Com um banco configurado, os comandos individuais são:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.test
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py migrate --check
.venv/bin/python manage.py test tests --noinput --verbosity 2
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
```

Para executar migrations em `development`, defina uma chave própria em `DJANGO_SECRET_KEY`. A chave pública do módulo `test` serve somente aos testes; não há configuração de deploy nesta entrega.

## Resultados e limites

O registro da execução final está em [evidências da Etapa 2](etapa-02-evidencias.txt). A revisão deve consultar a saída real, inclusive versões e códigos de saída. O tempo mostrado pelo runner é duração dos testes, não uma medição de desempenho do sistema.

Execução final em 23/10/2026, às 18:54, no fuso `America/Sao_Paulo` (21:54 UTC), com Python 3.12.15 e PostgreSQL 17.11:

| Verificação | Resultado real |
| --- | --- |
| `pip check` | Nenhuma dependência incompatível detectada |
| `ruff check .` | Aprovado |
| `ruff format --check .` | 37 arquivos Python já formatados |
| `manage.py check` | Nenhum problema detectado |
| `makemigrations --check --dry-run` | Nenhuma mudança de modelos sem migration |
| `migrate --noinput` e `migrate --check` | Banco atualizado, sem migrations pendentes |
| `manage.py test tests --noinput --verbosity 2` | 27 testes aprovados; banco de teste criado do zero com todas as migrations e removido ao terminar |

Todos esses comandos retornaram código zero. O banco principal local já havia recebido as quatro migrations iniciais; a execução final não precisou reaplicá-las nele. A criação de `test_loja` reaplicou todas as migrations em banco novo, como registrado na saída.

Na execução inicial, quatro subcasos de `NaN` falharam porque o teste esperava uma exceção do banco, mas o ORM já rejeitava o valor com `ValidationError`. O teste foi corrigido para enviar valores por SQL parametrizado, alcançando os checks do PostgreSQL. Não foi necessário enfraquecer uma restrição nem mudar a regra de negócio.

Cobertura atual: quantidades e limites; saldo negativo; duplicidades; representação monetária; `NaN` no banco; snapshot de catálogo; endereço e moeda; 96 combinações de estado/presença de datas; ordem temporal; pagamento único, referência única e simulação obrigatória; entrega única; 30 combinações de tipo/sinal/contexto de movimento; unicidade de reserva/liberação; justificativa; proteção de exclusão e chaves estrangeiras; datas com fuso; hash, email e configuração de superusuário.

As 96 combinações e as 30 combinações são subcasos dentro de métodos de teste, não testes independentes adicionais. Ainda não existem testes de endpoints, JWT, autorização por objeto, transações de compra, rollback após reserva, cancelamento/pagamento idempotente, concorrência de negócios ou relatórios. Eles dependem das implementações das etapas seguintes e não são declarados aprovados nesta entrega.
