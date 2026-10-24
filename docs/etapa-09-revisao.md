# Revisão técnica — Etapa 9

Situação: aprovada com uma correção obrigatória resolvida; consulte o [parecer final](etapa-09-parecer.md). A Etapa 10 não foi iniciada.

## Solicitação e requisitos

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

Escopo: Etapa 9, página 6 do PDF de especificação, preservando as regras das etapas anteriores. O PDF original não integra o repositório público. O [relatório](etapa-09-desempenho.md) registra volume/distribuição, comandos, protocolo, índices existentes, hipóteses, medições, custos, N+1 e limites. O [JSON](etapa-09-planos.json) contém todos os planos reais, SQL, parâmetros, amostras e hashes de resultado. As [evidências](etapa-09-evidencias.txt) preservam as saídas das verificações.

## Arquivos alterados

| Arquivo | Responsabilidade |
| --- | --- |
| `benchmarks/__init__.py` | Módulo local de experimentos, sem rota HTTP |
| `benchmarks/dataset.py` | Guardas de isolamento, volumes limitados, carga fictícia transacional pelos serviços e calendário fixo |
| `benchmarks/audit.py` | Auditoria de sete grupos de invariantes e distribuição dos dados |
| `benchmarks/runner.py` | Consultas ORM, fases de índices, EXPLAIN, hashes, custos e contagem N+1/HTTP |
| `scripts/benchmark_stage9.py` | Criação de banco novo, processo isolado, migrations e limpeza do banco pertencente à execução |
| `orders/models.py` | Dois índices justificados pelas medições |
| `orders/migrations/0002_stage9_query_indexes.py` | Adição reversível dos dois índices, sem alterar registros ou restrições |
| `reports/selectors.py` | Extração do agregado diário para reutilização exata no benchmark |
| `tests/test_benchmarks.py` | 20 testes de isolamento, rollback, determinismo, auditoria, leitura e contagem de consultas |
| `README.md` | Situação e links da entrega |
| `docs/etapa-09-desempenho.md` | Explicação acessível, decisões, resultados reais, comandos e limites |
| `docs/etapa-09-planos.json` | Evidência bruta de 245 execuções medidas, além de 70 aquecimentos |
| `docs/etapa-09-evidencias.txt` | Checks, 248 testes finais locais, 248 no Docker, execução e preservação da demonstração |
| Este arquivo e `docs/etapa-09-parecer.md` | Critérios e resultado da revisão |

## Decisões para conferir

- O comando só apaga o nome aleatório que criou; não reutiliza banco, não varre bancos para limpeza e não usa `FORCE`.
- A função geradora exige base de domínio vazia, prefixo e nome esperados; não redefine usuários ou estoque existentes.
- Usuários usam `@example.com`, senhas inutilizáveis e nenhum token/segredo é exportado. Pagamentos continuam simulados, sem cobrança real.
- Serviços de domínio preservam a lógica transacional; a alteração de datas/referências é exclusiva da fixture, depois das transições e na mesma transação externa.
- Auditoria e hash integral verificam que as fases de consulta e a medição HTTP não alteraram os registros.
- A carga maior foi executada em outro banco e removida. O hash dos nove modelos da demonstração permaneceu igual antes/depois e após a migration; saldos 26/17/45.
- PKs, unicidades e FKs existentes foram inventariadas; não houve remoção de restrições nem índices indiscriminados.
- O índice de pagamento atende intervalos seletivos; o parcial de pendências atende filtro/ordenação/limite. A consulta anual preserva varredura, sem ganho demonstrável.
- Fases comparáveis, cache aquecido, mesma carga, um `ANALYZE` explícito e estimativas registradas, duas bases sem candidatos, sete repetições e todos os planos preservados. Sem desativar varreduras sequenciais para forçar resultado.
- Medianas, intervalos, buffers, espaço e construção são medidas reais. Custo de escrita/concorrência não foi medido. Não há promessa de latência de produção ou ganho universal.
- N+1 é demonstrado pelo serializer simples; a implementação otimizada da Etapa 7 já existia. Conteúdo igual e contagens constantes até a página máxima foram verificados.
- Sem alterações de dependências, contrato HTTP, CI ou deploy. A Etapa 10 permanece pendente.

## Verificações realizadas

A suíte completa passou com **248 testes locais e 248 no Docker**, incluindo 20 novos, após a correção da revisão. Antes dela, passaram 247 em cada ambiente. `pip check`, Ruff, formatação, checks Django, consistência de migrations e OpenAPI validado sem avisos também passaram. O relatório não transforma os tempos da suíte em medidas de desempenho.

O gerador foi ensaiado com 100 pedidos no PostgreSQL local. A primeira execução maior confirmou os candidatos; uma segunda execução Docker com a migration final produziu o JSON publicado. As duas cargas grandes tiveram 20.000 pedidos, 500 clientes, 1.000 produtos, 40.094 itens e 18.000 pagamentos simulados. Somente a segunda medição fundamenta as tabelas finais; não há escolha da melhor amostra entre execuções.

Antes da publicação, executar o scanner de privacidade e `git diff --check`. Mensagens de commit e textos descrevem meu desenvolvimento, mantendo as evidências técnicas verificáveis. O parecer deve diferenciar conferência de resultados registrados de nova execução da suíte.

## Correção da revisão

A conferência identificou uma corrida entre a verificação inicial de existência do arquivo e a gravação final por `write_text()`: duas execuções poderiam passar pela guarda e a segunda truncar a primeira evidência. O filho agora chama `write_result()` com `open("x")`, que cria exclusivamente o caminho. O teste reproduz a intercalação das duas guardas antes da primeira escrita, exige `FileExistsError` na segunda e confere o conteúdo preservado. A suíte completa foi repetida nos dois ambientes.

A conferência focada aprovou a correção e executou o teste isolado com êxito. A conferência geral do código e das 245 amostras não identificou outro bloqueador. A sugestão de publicar um temporário completo ficou opcional, com a possibilidade de JSON parcial após interrupção documentada. A correção de saída não altera SQL, dados ou medições já preservadas.
