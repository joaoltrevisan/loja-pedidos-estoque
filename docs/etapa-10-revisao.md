# Revisão técnica — Etapa 10

Situação: aprovada sem correções obrigatórias; consulte o [parecer final](etapa-10-parecer.md). A Etapa 11 não foi iniciada.

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

Escopo: Etapa 10, páginas 6–7 do PDF; requisitos de segurança, histórico, transações e pagamentos simulados das etapas anteriores. O PDF original não integra o repositório público. A [matriz de riscos e decisões](etapa-10-testes-ci.md) identifica testes concretos para cada requisito.

## Arquivos alterados

| Arquivo | Responsabilidade |
| --- | --- |
| `.github/workflows/ci.yml` | CI com PostgreSQL 17, role não superusuária, dependências fixadas, estilo, migrations, suíte completa, OpenAPI e inspeção de publicação |
| `tests/test_api_concurrency.py` | Três testes concorrentes pelas rotas reais da API, JWT, PIDs independentes, bloqueios observados e auditoria de histórico/saldo |
| `README.md` | Situação, comandos e links da etapa |
| `docs/etapa-10-testes-ci.md` | Matriz dos 15 riscos, desenho dos testes/CI, referências e limites |
| `docs/etapa-10-evidencias.txt` | Resultados reais de testes e verificações, com caminhos locais anonimizados |
| Este arquivo e `docs/etapa-10-parecer.md` | Critérios, achados e fechamento da revisão |

Não há alteração de modelos, migrations, serviços, dependências ou contratos HTTP.

## Critérios para conferir

- Os riscos exigidos já testados permanecem na suíte completa; os três novos casos exercitam a integração da API, sem duplicar indiscriminadamente a cobertura existente.
- JWT não é substituído por autenticação forçada; cada requisição usa cliente próprio e credenciais fictícias.
- A concorrência depende de conexões PostgreSQL distintas, pausa controlada depois do lock e observação de `pg_blocking_pids`, sem SQLite ou simples sequenciamento.
- Confere respostas 201/409 ou 200/409 e também o estado persistido, quantidade de registros, razão de estoque e histórico coerente.
- CI usa conta regular; somente bootstrap usa postgres no serviço recém-criado. Não recebe `.env` ou segredo pessoal.
- Actions oficiais por SHA, permissões de leitura, credenciais não persistidas, sem `pull_request_target`, escrita externa ou deploy.
- Falhas de estilo, migrations, teste, OpenAPI ou scanner encerram o job; não há `continue-on-error`, exclusão de concorrência ou substituição por banco em memória.
- Ensaio Docker é distinguido de execução hospedada real; esta deve ser conferida no SHA do commit enviado.
- Preservação da demonstração e remoção dos recursos temporários registradas. A revisão não deve alterar código ou dados.

## Verificações registradas

251 testes passaram no PostgreSQL local e 251 no ensaio Docker isolado. Pip/Ruff/formatação/Django/migrations/OpenAPI passaram, assim como o actionlint local. A suíte anterior tinha 248 casos; os três novos correspondem a última unidade e às duas ordens de pagamento/cancelamento via HTTP em processo.

A conferência deve distinguir a leitura das evidências de repetir testes ou disparar uma execução remota. A execução hospedada 40135509840 terminou com `success` no SHA `2f0fa3d20e2ed7cc225d9d3f0d1e7407571984e2`; todas as etapas passaram e o log confirma 251 testes. O parecer final registra o alcance e a sugestão opcional. Não iniciar a Etapa 11 nesta revisão.
