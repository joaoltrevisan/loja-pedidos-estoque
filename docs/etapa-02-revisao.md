# Etapa 2 — Pacote de revisão técnica

## Critérios da revisão técnica

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

PDF de referência neste computador: `documento de requisitos fornecido pelo usuario (PDF externo ao repositorio)`. Comparar especialmente as páginas 2–3, Etapa 2; usar as regras de domínio das páginas 1–2 e as exigências gerais como contexto.

## Escopo entregue

Diagrama detalhado antes dos modelos, usuário customizado desde a migration inicial, entidades mínimas, quatro migrations, restrições locais, relações históricas protegidas, dinheiro decimal, datas com fuso e testes no PostgreSQL. Somente o ambiente mínimo indispensável à verificação foi antecipado da Etapa 3, conforme a dependência documentada na Etapa 1.

O projeto está em `loja-pedidos-estoque`. Os demais projetos da pasta de trabalho não fazem parte desta entrega. Os arquivos ainda não têm uma base de commits própria, portanto a revisão deve ler os arquivos atuais, e não depender apenas de `git diff`.

Decisões e limites: [modelagem](etapa-02-modelagem.md). Versões, instruções e cobertura: [validação](etapa-02-validacao.md). Saída real dos comandos: [evidências](etapa-02-evidencias.txt).

## Arquivos da entrega

`README.md` foi atualizado. Os demais arquivos abaixo foram criados nesta etapa. A documentação da Etapa 1 foi preservada.

| Arquivo | Mudança |
| --- | --- |
| [.gitignore](../.gitignore) | Criado |
| [.python-version](../.python-version) | Criado |
| [README.md](../README.md) | Atualizado |
| [accounts/__init__.py](../accounts/__init__.py) | Criado |
| [accounts/managers.py](../accounts/managers.py) | Criado |
| [accounts/migrations/0001_initial.py](../accounts/migrations/0001_initial.py) | Criado |
| [accounts/migrations/__init__.py](../accounts/migrations/__init__.py) | Criado |
| [accounts/models.py](../accounts/models.py) | Criado |
| [catalog/__init__.py](../catalog/__init__.py) | Criado |
| [catalog/migrations/0001_initial.py](../catalog/migrations/0001_initial.py) | Criado |
| [catalog/migrations/__init__.py](../catalog/migrations/__init__.py) | Criado |
| [catalog/models.py](../catalog/models.py) | Criado |
| [common/__init__.py](../common/__init__.py) | Criado |
| [common/fields.py](../common/fields.py) | Criado |
| [common/limits.py](../common/limits.py) | Criado |
| [common/models.py](../common/models.py) | Criado |
| [config/__init__.py](../config/__init__.py) | Criado |
| [config/settings/__init__.py](../config/settings/__init__.py) | Criado |
| [config/settings/base.py](../config/settings/base.py) | Criado |
| [config/settings/development.py](../config/settings/development.py) | Criado |
| [config/settings/test.py](../config/settings/test.py) | Criado |
| [config/urls.py](../config/urls.py) | Criado |
| [docs/etapa-02-evidencias.txt](../docs/etapa-02-evidencias.txt) | Criado |
| [docs/etapa-02-modelagem.md](../docs/etapa-02-modelagem.md) | Criado |
| [docs/etapa-02-revisao.md](../docs/etapa-02-revisao.md) | Criado |
| [docs/etapa-02-validacao.md](../docs/etapa-02-validacao.md) | Criado |
| [inventory/__init__.py](../inventory/__init__.py) | Criado |
| [inventory/migrations/0001_initial.py](../inventory/migrations/0001_initial.py) | Criado |
| [inventory/migrations/__init__.py](../inventory/migrations/__init__.py) | Criado |
| [inventory/models.py](../inventory/models.py) | Criado |
| [manage.py](../manage.py) | Criado |
| [orders/__init__.py](../orders/__init__.py) | Criado |
| [orders/migrations/0001_initial.py](../orders/migrations/0001_initial.py) | Criado |
| [orders/migrations/__init__.py](../orders/migrations/__init__.py) | Criado |
| [orders/models.py](../orders/models.py) | Criado |
| [pyproject.toml](../pyproject.toml) | Criado |
| [requirements-dev.txt](../requirements-dev.txt) | Criado |
| [requirements.lock](../requirements.lock) | Criado |
| [requirements.txt](../requirements.txt) | Criado |
| [scripts/local_postgres.py](../scripts/local_postgres.py) | Criado |
| [scripts/verify_stage2.py](../scripts/verify_stage2.py) | Criado |
| [tests/__init__.py](../tests/__init__.py) | Criado |
| [tests/test_schema.py](../tests/test_schema.py) | Criado |


`.local` contém instalações, cluster e logs de trabalho, todos ignorados; `.venv` contém o ambiente virtual. Não fazem parte do código para versionamento. Nenhum commit, push, PR, publicação ou deploy foi realizado.

## Pontos para orientar a revisão

- Verificar se os checks correspondem à documentação e se as migrations os aplicam realmente no PostgreSQL.
- Conferir a distinção entre “no máximo um” garantido por unicidade e “exatamente um”/existência de itens, que dependerá de serviços.
- Conferir campos históricos, exclusão protegida, simulação obrigatória e limites de precisão.
- Revisar checks com datas opcionais, considerando que `NULL` pode enfraquecer uma expressão SQL se a presença não for verificada separadamente.
- Verificar testes que contornam `full_clean()` e testes com SQL direto, além dos exemplos válidos.
- Não assumir que checks locais garantem autorização, total agregado, transições, saldo conciliado com movimentos ou bloqueios de concorrência. Esses serviços ainda não existem; avaliar se o esquema permite implementá-los corretamente.
- Avaliar os limites explícitos da configuração local, sem confundi-la com a futura execução por Docker Compose.

## Situação de revisão

Revisão técnica concluída: [parecer independente](etapa-02-parecer.md). Sem correções obrigatórias ou bloqueadores para a Etapa 3; os 27 testes foram repetidos com êxito. O código não foi alterado durante a revisão.
