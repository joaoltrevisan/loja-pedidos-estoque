# Parecer técnico — Etapa 10

Data: 24/10/2026.

**Resultado: aprovada no escopo revisado, sem correções obrigatórias pendentes, com a execução hospedada conferida.** A Etapa 11 não foi iniciada.

## Revisão local

A revisão comparou as páginas 6–7 do PDF com o workflow, os três testes novos, o helper de concorrência, os testes anteriores e as evidências, conforme os [critérios](etapa-10-revisao.md). Foi somente de leitura: não alterou arquivos, dados ou containers e não repetiu a suíte.

A matriz do [guia](etapa-10-testes-ci.md) aponta testes concretos para os 15 riscos pedidos. Foram conferidos casos de rejeição de entradas, adulteração, autorização, rollback, idempotência, preços históricos e limites de faturamento. Não foi identificado requisito obrigatório ausente.

Os novos testes usam PostgreSQL, `TransactionTestCase`, JWT e clientes independentes nas rotas da aplicação. O helper exige PIDs distintos e observa a segunda conexão bloqueada pela primeira antes de liberá-la. Além do HTTP, os testes conferem saldo, movimentos, pagamento, estado e integridade entre tabelas. Não foi substituída a concorrência por SQLite, autenticação forçada ou chamadas sequenciais.

O workflow tem permissões de leitura, checkout sem credenciais persistidas e Actions oficiais por SHA. O bootstrap usa postgres somente no serviço temporário; a suíte usa role comum. Os comandos não mascaram falhas de dependências, estilo, migrations, testes, contrato ou scanner. Não há publicação de imagem ou deploy.

Foram conferidos os registros de **251 testes locais e 251 no Docker**, três testes isolados, actionlint e preservação da demonstração. Esses registros foram distinguidos da execução hospedada.

## Conferência hospedada

A conferência final identificou a [execução hospedada 40135509840](https://github.com/joaoltrevisan/loja-pedidos-estoque/actions/runs/40135509840), correspondente ao SHA `2f0fa3d20e2ed7cc225d9d3f0d1e7407571984e2`, também confirmado no checkout registrado no log. O run, o job e todos os passos oficiais terminaram com `success`.

Foi conferida a instalação efetiva de `requirements.lock`, bootstrap, dependências, estilo, migrations, criação/remoção de `test_loja_ci`, **251 testes aprovados em 41,442 s**, validação e comparação OpenAPI e scanner aprovado para **158 arquivos daquele commit**. O scanner no estado documental atual aprovou **162 candidatos**, uma contagem de outro momento. A revisão final verificou logs/metadados e executou somente esse scanner, sem repetir testes ou alterar arquivos, dados e containers.

Os trechos da CLI trazem `UNKNOWN STEP`; os nomes e conclusões corretos constam dos metadados oficiais preservados nas [evidências](etapa-10-evidencias.txt). Os 41,442 s são duração da suíte, sem conclusão sobre desempenho da aplicação.

A aprovação refere-se ao código e SHA conferidos. O commit posterior apenas de documentação terá sua própria CI, acompanhada até o resultado final.

## Sugestão opcional

Fixar também o digest da imagem PostgreSQL em `.github/workflows/ci.yml` aumentaria a reprodutibilidade diante de atualização da tag. Para verificar essa mudança, seria necessário escolher o digest oficial correspondente e repetir a CI. A versão explícita atual e a limitação documentada são suficientes para esta entrega; a sugestão não é um bloqueador.

## Limites

O workflow não configura proteção da branch nem transforma os testes em prova de todos os escalonamentos concorrentes. Não há porcentagem de cobertura medida, teste de carga, auditoria de vulnerabilidades ou validação de produção. Dados e pagamentos permanecem fictícios/simulados, sem cobrança real.
