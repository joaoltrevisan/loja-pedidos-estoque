# Parecer técnico — Etapa 9

Data: 24/10/2026.

**Resultado: aprovada após uma correção obrigatória, sem bloqueadores pendentes.** A Etapa 10 não foi iniciada.

## Alcance e resultado

A revisão comparou a Etapa 9 do PDF com o gerador, isolamento e limpeza, auditoria, consultas, planos, migration, testes e relatório, conforme os [critérios documentados](etapa-09-revisao.md). Não houve alteração de código, dados ou containers durante a revisão.

A conferência do JSON recalculou as medianas, mínimos e máximos das **245 amostras**, confirmou as tabelas do relatório, os tamanhos e custos de construção, a contagem N+1 e os buffers. A auditoria tem zero violações nos sete grupos e o hash integral do domínio é igual antes e depois. Essa conferência analisou os registros, sem repetir a carga maior ou a suíte completa.

Os dois índices estão justificados na distribuição medida. As consultas anual, por cliente, por chave primária e de estoque baixo não apresentam ganho demonstrável com os candidatos. A documentação separa redução de trabalho, tempo absoluto local e ausência de garantia para produção. Índices existentes de PK, unicidade e FK foram considerados; nenhuma restrição foi removida.

## Problema corrigido

**Arquivo:** `scripts/benchmark_stage9.py`, gravação final da saída.

**Impacto:** a guarda inicial `output.exists()` ocorria antes dos minutos de geração e medição. Duas execuções com o mesmo caminho podiam passar por ela; `write_text()` no filho truncaria silenciosamente o primeiro resultado quando a segunda terminasse.

**Correção:** o filho chama `write_result()`, que abre o caminho com modo `x`. A criação exclusiva permite que apenas uma gravação crie o arquivo. A outra recebe `FileExistsError`, preservando o conteúdo anterior. A limpeza do banco pertencente à execução permanece no `finally` do pai.

**Como verificar:** executar `test_final_write_preserves_evidence_when_two_parent_checks_pass`, em `tests/test_benchmarks.py`. Ele reproduz deterministicamente a intercalação: duas guardas passam, a primeira escrita conclui, a segunda falha e o conteúdo original permanece. Não é um teste de desempenho nem uma simulação de carga concorrente no banco.

A conferência focada aprovou o fechamento desse achado e executou **1 teste com êxito**, sem criar banco de testes. Não reavaliou os demais arquivos nem repetiu a carga ou a suíte completa. O SQL e as medições preservadas não foram alterados por essa correção.

## Verificações finais

Após a correção, a execução completa registrou **248 testes aprovados no PostgreSQL local e 248 no Docker**. As [evidências](etapa-09-evidencias.txt) preservam tanto os 247 testes anteriores quanto os 248 finais, sem substituir resultados antigos por números novos. Dependências, Ruff, formatação, Django, migrations e OpenAPI foram conferidos com êxito.

O benchmark maior usou banco separado e foi removido. A demonstração manteve os mesmos registros e saldos após o experimento e após a migration. A aplicação local respondeu `200` em `/health/`; nenhum banco `loja_bench_…` permaneceu no servidor Docker conferido.

## Sugestão opcional e limites

Publicar somente um arquivo temporário já completo, com recusa de sobrescrita na publicação, evitaria JSON parcial se o processo for interrompido durante a gravação. Essa melhoria não bloqueia o fechamento do achado: a evidência anterior já está protegida. A limitação e a necessidade de usar apenas saídas concluídas/JSON válido estão documentadas.

Não foram medidos custo de escrita, throughput, cache frio, carga concorrente ou latência de produção. Não há promessa de ganho universal nem validação de migração sem interrupção em produção. Estatísticas estimadas podem variar ligeiramente entre fases e estão preservadas nos planos. Pagamentos continuam simulados, sem cobrança real. A publicação do código é separada da revisão; não há deploy público da aplicação.
