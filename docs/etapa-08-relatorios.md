# Etapa 8 — Consultas e relatórios de negócio

Etapa em desenvolvimento. Este primeiro registro define o contrato e os valores de referência; a entrega final depende das verificações da API, do Docker e da revisão técnica. Não há medição de desempenho nesta etapa.

Todos os indicadores financeiros são **SIMULADOS, SEM COBRANÇA REAL**. Faturamento aqui é um nome para a soma dos pagamentos simulados aprovados; não constitui apuração contábil ou fiscal.

## Critérios dos indicadores

| Indicador | Critério |
| --- | --- |
| Faturamento diário/mensal | Soma dos pagamentos simulados aprovados no período, de pedidos hoje em PAID, SHIPPED ou DELIVERED; agrupa pela data de aprovação no fuso definido |
| Produtos mais vendidos | Soma das quantidades dos itens desses pedidos; valor é quantidade × preço histórico, sem usar o preço atual |
| Clientes com maior valor comprado | Soma desses pagamentos por identificador do cliente, sem multiplicar o valor pelo número de itens |
| Ticket médio | Soma dos pagamentos / quantidade de pagamentos, arredondando para centavos com HALF_UP |
| Estoque baixo | Produtos ativos cujo saldo disponível atual é menor ou igual ao limite informado |
| Pedidos por status | Conta estados atuais dos pedidos criados no período; usa criação, não aprovação de pagamento |
| Pendências antigas | Somente PENDING_PAYMENT, por criação e ID, com idade mínima opcional; não cancela nem expira reservas |

Os relatórios são exclusivos do administrador, inclusive quando chamados diretamente na camada de consultas. Os filtros de papel consultam o usuário atual no banco. Consultas não corrigem nem alteram dados do domínio.

## Datas, limites e valores vazios

`start` e `end` são datas de calendário no formato `YYYY-MM-DD`. O intervalo usa início inclusivo e fim exclusivo: `[start, end)`. O período deve conter de 1 a 366 dias. Os limites de meia-noite são interpretados em `America/Sao_Paulo` e convertidos para UTC na comparação com os instantes do banco. A data de agrupamento usa explicitamente o mesmo fuso, independentemente do fuso ativo na requisição.

Dias sem pagamento aparecem com `0.00` e contagem zero. Meses são meses de calendário; um mês parcialmente coberto inclui somente pagamentos dentro do intervalo pedido. Séries mensais também preenchem meses vazios. Não há divisão por zero: ticket médio sem pagamentos é `0.00`. Rankings e listas vazias retornam `results=[]`; estados sem pedidos retornam contagem zero, mantendo os cinco estados.

O total e a série do faturamento vêm da mesma consulta agrupada por dia. Os meses são consolidados sobre esses dias, no máximo 366, usando Decimal. Assim uma aprovação concorrente não pode entrar no total e faltar na série da mesma resposta. Relatórios diferentes e páginas diferentes podem observar instantes distintos sob o isolamento READ COMMITTED; não se promete um snapshot global entre requisições.

## Histórico e identificação

O agrupamento dos produtos usa `product_id`, mesmo se SKU ou nome mudarem. A resposta usa SKU/nome atuais para identificar o produto, mas valores vendidos usam sempre `OrderItem.unit_price`. Produtos atualmente inativos continuam aparecendo em vendas anteriores. O relatório de estoque baixo, por outro lado, consulta somente os ativos atuais.

Clientes são agrupados por `customer_id`, com nome atual; os rankings não retornam email, telefone, senha ou endereço. Pedidos preservam seus próprios snapshots históricos.

## Conjunto pequeno de referência

O conjunto de testes usa produtos e clientes fictícios. No intervalo `[2026-01-01, 2026-02-01)` em São Paulo:

| Operação | Resultado esperado |
| --- | --- |
| Pedido criado em dezembro, pagamento aprovado exatamente em 01/01 00:00 | Entra com 3 × 25.90 = 77.70 |
| Pedido com duas linhas, pagamento aprovado em 02/01 00:00 | Entra com 1 × 29.80 + 2 × 0.10 = 30.00 |
| Pagamento em 31/12 23:59:59.999999 | Fica fora do início |
| Pagamento exatamente em 01/02 00:00 | Fica fora do fim |
| Pedido pendente e pedido cancelado | Não entram no faturamento |
| Faturamento | 107.70, dois pagamentos |
| Ticket médio | 53.85 |
| Primeiro produto | 4 unidades, valor histórico 107.50 |
| Segundo produto | 2 unidades, valor histórico 0.20 |

O preço atual do primeiro produto é alterado para `99.99` e seu nome/SKU mudam depois das compras; os valores acima devem permanecer iguais. Os testes também incluem centavo exatamente antes do fim, virada de dia em UTC versus São Paulo, ano bissexto, fronteira histórica de horário de verão e arredondamento de `2.01 / 2` para `1.01`.

Esses valores definem as expectativas conferidas pelos testes; os registros reais de execução serão anexados ao pacote final de revisão.
