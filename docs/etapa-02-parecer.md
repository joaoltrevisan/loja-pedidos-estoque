# Parecer técnico da Etapa 2

Revisão técnica em 23/10/2026, usando os critérios documentados de revisão. O revisor leu as sete páginas do PDF, os modelos, as quatro migrations, configurações, scripts, testes e documentação. Não alterou arquivos.

**Resultado: aprovado, sem problemas obrigatórios identificados e sem bloqueadores para a Etapa 3.** Isso é um parecer técnico dentro do escopo da etapa, não garantia de ausência de todo defeito.

O revisor repetiu os 27 testes no PostgreSQL real: todos passaram, com banco `test_loja` criado do zero e removido ao terminar. Também repetiu `makemigrations --check --dry-run` (sem mudanças) e `migrate --check` (sem pendências). Todos esses comandos retornaram código zero. O servidor local foi encerrado.

Sugestão opcional: ampliar os testes de máximos monetários para `OrderItem.unit_price` e `SimulatedPayment.amount` e testar valores acima da precisão por SQL parametrizado. Impacto: aumentar a cobertura contra regressões; os tipos atuais já oferecem a proteção. Verificação futura: máximos válidos persistem exatamente e valores fora da precisão são rejeitados no PostgreSQL.

Limites: não foram comprovados autorização de API, idempotência, rollback de compras, concorrência de negócio ou desempenho; essas funcionalidades ainda não existem. Sem histórico de versões próprio, a revisão não pode provar a ordem histórica de criação do diagrama e das migrations; seu conteúdo final é coerente.

A geração de demonstração da Etapa 3 deve verificar explicitamente as invariantes entre tabelas. O esquema isolado não obriga a existência de itens, pagamentos, entregas e movimentos compatíveis com o estado de cada pedido.
