# Parecer técnico — Etapa 7

Data: 24/10/2026.

**Resultado: aprovada no escopo operacional documentado, sem bloqueadores pendentes.** O problema obrigatório encontrado na paginação foi corrigido e verificado. A Etapa 8 não foi iniciada.

Revisão técnica da implementação, conforme os critérios de revisão reproduzidos no [pacote de revisão](etapa-07-revisao.md). A revisão comparou os arquivos atuais aos requisitos do PDF e às decisões documentadas. O revisor não alterou arquivos, dados ou containers e não repetiu a suíte completa.

## Problema obrigatório corrigido

**P2 — validação e paginação interpretavam entradas de forma diferente.**

Arquivos: `common/api.py` e `common/queries.py`; aplicação dos campos de query também em `inventory/serializers.py` e `orders/serializers.py`.

Antes da correção, `page_size=1.0` era validado como 1, mas o paginador relia o texto original e usava silenciosamente o padrão 20. `page=1.0` também passava pela validação e resultava em comportamento diferente no paginador. O impacto era uma resposta que não correspondia à entrada validada, prejudicando o contrato de paginação.

A correção exige somente dígitos ASCII nos parâmetros inteiros. Valores decimais aparentando inteiros, sinais, espaços, expoentes e dígitos Unicode são rejeitados com 400 antes da paginação.

Verificação: o revisor conferiu o código e reproduziu em memória a rejeição de `page_size=1.0`. O teste `test_pagination_rejects_decimal_text_consistently_across_all_lists` cobre as quatro listas para `page` e `page_size`; as evidências finais incluem a recusa por HTTP de `page=1.0` e `page_size=1.00` em todas elas. Repeti a suíte completa após a correção.

## Demais conclusões

Não foram identificados outros problemas obrigatórios em catálogo, estoque, autorização, consulta de pedidos ou transações. Produto e estoque inicial são criados juntos; saldo e movimento confirmam atomicamente; os bloqueios seguem o protocolo das compras; clientes não consultam pedidos alheios; campos protegidos, filtros e ordenação são controlados.

O revisor conferiu as [evidências finais](etapa-07-evidencias.txt): **191 testes locais e 191 no Docker aprovados**, checks e fluxo HTTP isolado, com demonstração principal preservada.

Executou adicionalmente, sem gravar dados:

- Geração OpenAPI com `--validate --fail-on-warn`, código zero e sem avisos; conteúdo equivalente ao arquivo exportado.
- Scanner de publicação, aprovado para os 126 arquivos candidatos presentes naquele momento.
- Inspeção visual da captura do Swagger, sem credenciais ou dados pessoais visíveis.

Nenhuma sugestão opcional nova que justifique ampliar esta entrega.

## Limites

Relatórios e sua documentação permanecem pendentes para a Etapa 8, conforme a dependência explicada antes da implementação. A aprovação não declara a API final completa, desempenho medido ou prontidão para produção.

O scanner examina o conteúdo atual; não constitui garantia absoluta sobre histórico ou publicação futura. O revisor não realizou commit nem envio ao GitHub. A publicação do código é uma atividade separada desta revisão; não inclui deploy da aplicação.
