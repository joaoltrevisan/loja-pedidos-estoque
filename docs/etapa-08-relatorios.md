# Etapa 8 — Consultas e relatórios de negócio

Consultas e API implementadas, verificadas no PostgreSQL local e Docker e aprovadas em revisão técnica. Não há medição de desempenho nesta etapa.

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

Esses valores foram conferidos pelos testes; os registros reais de execução estão nas [evidências](etapa-08-evidencias.txt), com [arquivos e decisões](etapa-08-revisao.md) e [parecer aprovado](etapa-08-parecer.md).

## Rotas e parâmetros

Todas as rotas abaixo usam `GET`, exigem JWT de administrador e retornam dados com `Cache-Control: no-store`. Não oferecem operações de escrita. Os erros seguem o envelope `code`, `detail` e `errors` já usado na API.

| Rota sob `/api/reports/` | Filtros | Ordenação permitida |
| --- | --- | --- |
| `revenue/` | `start`, `end`; `group_by=day` ou `month` | Série cronológica, sem paginação; até 366 dias |
| `average-ticket/` | `start`, `end` | Resultado agregado único |
| `top-products/` | `start`, `end`, paginação | `product_id`, `units_sold`, `simulated_revenue`; padrão `-units_sold`, desempate por produto |
| `top-customers/` | `start`, `end`, paginação | `customer_id`, `paid_orders`, `simulated_revenue`; padrão `-simulated_revenue`, desempate por cliente |
| `low-stock/` | `threshold` inteiro obrigatório entre 0 e 2147483647, paginação | `product_id`, `available_quantity`; padrão saldo crescente, desempate por produto |
| `orders-by-status/` | `start`, `end` | Cinco estados em ordem fixa, sem paginação |
| `oldest-pending/` | `min_age_hours` opcional entre 0 e 87600, padrão 0; paginação | `id`, `created_at`, `total`; padrão criação crescente, desempate por ID |

`start` e `end` são obrigatórios nas cinco consultas por período. Estoque baixo e pendências são retratos atuais e não aceitam filtros de período. O filtro de idade das pendências inclui exatamente a idade mínima e não inclui datas de criação futuras. A idade é calculada a partir do relógio do servidor, sem modificar o pedido.

Listas retornam `count`, `next`, `previous` e `results`, com página padrão 20 e `page_size` entre 1 e 100. A ordenação aceita até três campos, com `-` para descendente. Os parâmetros inteiros aceitam somente dígitos ASCII; valores como `page_size=1.0` são inválidos. Parâmetros desconhecidos, repetidos, vazios ou fora dos limites retornam 400. Página inexistente retorna 404. Clientes recebem 403; credencial ausente/inválida, 401; métodos de escrita, 405 para administrador autenticado.

## Reproduzir pela documentação e por curl

O [contrato OpenAPI](openapi.yaml) inclui as sete operações, perfis, parâmetros obrigatórios, exemplos fictícios e erros. Abra o Swagger local e use **Authorize** com o access token do administrador fictício. No ambiente padrão, a base é `http://127.0.0.1:8000`; na demonstração já preparada neste computador, a porta é `18003`.

Exemplos de consultas (o token deve ficar apenas no ambiente local):

```bash
curl --get "$BASE_URL/api/reports/revenue/" \
  -H "Authorization: Bearer $ADMIN_ACCESS" \
  --data-urlencode 'start=2026-01-01' \
  --data-urlencode 'end=2026-02-01' \
  --data-urlencode 'group_by=month'

curl --get "$BASE_URL/api/reports/top-products/" \
  -H "Authorization: Bearer $ADMIN_ACCESS" \
  --data-urlencode 'start=2026-01-01' \
  --data-urlencode 'end=2026-02-01' \
  --data-urlencode 'ordering=-simulated_revenue' \
  --data-urlencode 'page_size=10'

curl --get "$BASE_URL/api/reports/low-stock/" \
  -H "Authorization: Bearer $ADMIN_ACCESS" \
  --data-urlencode 'threshold=26'
```

Defina `BASE_URL` para sua porta e `ADMIN_ACCESS` com a resposta do login documentado na Etapa 4; não publique esses tokens. O limite de 366 dias é da API e da camada de consultas, não um resultado de medição de desempenho. Para consultar períodos maiores, faça janelas separadas; a média de um período maior deve ser calculada pela soma total dividida pela contagem total, não pela média simples dos tickets das janelas.

## Organização e consistência

`reports/periods.py` define o período e seu fuso; `reports/selectors.py` concentra os critérios e agregações com o ORM. Serializers validam entrada e apresentam Decimal como texto; views aplicam permissões e orquestram consultas; `reports/schema.py` mantém o contrato da API. Nenhum modelo, migration, índice ou dependência nova foi necessário.

O faturamento e o ticket médio consultam pagamentos, sem juntar os itens, para não somar um mesmo pagamento várias vezes. O ranking de produtos soma itens históricos; o de clientes soma pagamentos por cliente. A ordenação de agregados desempata pelo identificador do grupo: acrescentar o ID de um item à ordenação dividiria um grupo em várias linhas e produziria um ranking incorreto.

Os dois testes de concorrência dos relatórios usam conexões independentes e sincronização por eventos. Um mantém um pagamento não confirmado enquanto o relatório lê: o valor ainda não aparece. O outro confirma o pagamento depois que o SELECT do agregado executa e antes da apresentação: total, contagem e série continuam coerentes com o snapshot lido; uma consulta posterior observa o pagamento novo. Esses testes verificam consistência de leitura, sem medir desempenho.

As consultas seguem os mecanismos de agregação e de [conversão de datas por fuso do Django](https://docs.djangoproject.com/en/5.2/ref/models/database-functions/#truncdate). O [guia oficial de agregações](https://docs.djangoproject.com/en/5.2/topics/db/aggregation/) orienta a separação entre filtros, agrupamento e agregados. Não foram criados índices sem medições, nem alterado o isolamento do PostgreSQL.

## Verificações e limites

A suíte tem **228 testes**: 191 anteriores e 37 novos (19 de consultas, 16 da API e 2 de concorrência de leitura). Os testes conferem limites de período, totais conhecidos, histórico, inativos, empates, paginação, conjunto vazio, papéis atuais, ausência de escrita, campos de contato ausentes dos rankings e esquema OpenAPI. Todos passaram localmente e no Docker Linux ARM64; as evidências registram as execuções completas.

O conjunto HTTP do gerador padrão difere do conjunto unitário acima. Foram conferidos em janeiro de 2026 **168.10 em três pagamentos**, ticket **56.03**, cinco estados com um pedido cada e saldo baixo de 17 e 26 para limite 26. Um pagamento aprovado durante o ensaio para pedido criado em janeiro entrou no dia real da aprovação, preservando o faturamento de janeiro e o mês de criação na contagem por status. O snapshot principal permaneceu idêntico, e os recursos temporários foram removidos.

Relatórios não constituem auditoria de todas as invariantes entre tabelas: dependem dos serviços transacionais que mantêm o histórico e das restrições locais do banco. Não existe expiração de reservas. Sem medições, índices novos, validação de produção ou GitHub Actions nesta etapa; essas entregas permanecem nas etapas previstas. A Etapa 9 não foi iniciada.
