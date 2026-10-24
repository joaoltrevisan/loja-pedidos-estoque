# Etapa 9 — índices e medições

Situação: implementada, verificada e aprovada em revisão técnica após corrigir a proteção da saída concorrente. Pagamentos e valores de venda são **simulados, sem cobrança real**.

## O que estou investigando

Um índice é uma estrutura extra que permite localizar ou percorrer registros em uma ordem útil. Ele ocupa espaço e precisa acompanhar as escritas. Buscar poucas datas pode aproveitar essa estrutura; ler boa parte de uma tabela pode tornar uma varredura sequencial mais barata.

Preparei sete consultas representativas: pendências antigas, faturamento de um dia, faturamento anual, produtos mais vendidos em um dia, pedidos de um cliente, busca pela chave primária e estoque baixo. A implementação mede o SQL compilado pelo ORM. Extraí `daily_revenue()` para que o experimento use exatamente o agregado do relatório, sem copiar suas regras financeiras.

## Carga e isolamento

O comando cria um banco novo com nome aleatório `loja_bench_…`, aplica as migrations e gera a carga. Ao terminar, remove somente o banco que criou, inclusive quando o processo filho falha. Não usa `DROP DATABASE ... FORCE`, não procura outros bancos pelo prefixo e não reaproveita a demonstração. Precisa da permissão `CREATEDB`, já existente na role de desenvolvimento para os testes; não é um comando de produção.

O gerador também exige que o banco conectado corresponda ao nome esperado, tenha o prefixo reservado e esteja vazio. Um bloqueio consultivo serializa tentativas do próprio gerador. A carga inteira usa uma transação: falhas desfazem usuários, catálogo, pedidos e movimentos. Não há rota HTTP para gerar ou reposicionar dados.

Uso `seed=42`, datas fictícias de 2024–2025 e contas `@example.com` com senhas inutilizáveis. Aproximadamente 30% dos pedidos se concentram no último mês; o restante se distribui pelos dois anos. Um cliente concentra aproximadamente 20% dos pedidos; um produto aparece com maior frequência. Cada pedido tem de um a três produtos distintos e quantidades de um a cinco. Os primeiros 90% dos produtos podem ser comprados; os demais fornecem casos de estoque baixo. Após as vendas, 10% do catálogo fica inativo e muda de preço, preservando os valores históricos dos itens.

Os serviços existentes criam produtos, entradas, pedidos, pagamentos simulados, envios, entregas e cancelamentos. Somente depois dessas transições a fixture fixa datas e referências na mesma transação. A auditoria em conjuntos verifica saldo versus movimentos, totais versus itens, pagamento versus estado/valor/data, remessa versus datas e reservas/liberações versus produto, quantidade, ator e cronologia. Os testes também percorrem o histórico de todos os 100 pedidos do conjunto de teste.

Uma impressão SHA-256 dos nove modelos de domínio é comparada antes e depois da medição, além da auditoria. O hash comprova igualdade dos registros nessa execução; não é uma prova de autenticidade independente. Senhas, tokens e credenciais não são exportados.

## Protocolo

- PostgreSQL 17.11, Python 3.12.15, Django 5.2.18, Linux ARM64 no Docker Desktop local.
- `VACUUM (ANALYZE)` após a geração, sem alterar as preferências do planejador. A carga fica igual entre fases e não executo outro `ANALYZE` deliberadamente. Os planos registram pequenas diferenças de estimativa entre fases; não afirmo igualdade absoluta dos metadados estatísticos do PostgreSQL.
- Fases: sem candidatos, apenas data de pagamento, ambos, apenas pendências, novamente sem candidatos. A última fase ajuda a perceber deriva de tempo/cache.
- Cada consulta recebe dois aquecimentos por fase e sete execuções medidas. A ordem das consultas varia por rodada com seed fixa; a ordem das fases é fixa e está registrada.
- Uso `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`; preservo todos os planos, tempos de planejamento/execução, estimativas, linhas reais e buffers. Os resultados SQL precisam manter o mesmo SHA-256 em todas as fases.
- Os tempos resumidos são `Execution Time` do PostgreSQL, sem custo de rede, autenticação, serialização ou renderização. A contagem de consultas HTTP é um experimento separado.
- Cache aquecido, sem reiniciar o banco ou limpar cache do sistema operacional. Um bloco `hit` estava no buffer compartilhado; um bloco `read` não comprova, por si só, uma leitura física do disco. Uso os totais da raiz do plano para não contar buffers duas vezes entre pai e filhos.
- O banco é descartável e não recebe tráfego de usuários. Os testes Docker terminaram durante a geração, antes das fases de medição. Não há controle rígido de todo o trabalho do computador hospedeiro.

Se a migration final já criou os candidatos, o runner retira somente esses dois índices não únicos, exclusivamente do banco recém-criado, antes de medir a base anterior. Não remove índices de PK, unicidade ou FK.

## Índices avaliados

Já havia 21 índices nas tabelas de pedidos, catálogo e estoque. O inventário completo, com definição e tamanho de cada um, está no JSON de evidências. Inclui as PKs, o SKU único e seu índice para padrões, os relacionamentos um para um de estoque/pagamento/remessa, a referência única do pagamento, a unicidade pedido/produto dos itens e os índices de FKs. Não dupliquei esses acessos nem removi estruturas sem um experimento que justificasse a mudança.

| Candidato mantido | Motivo | Custo adicional |
| --- | --- | --- |
| `payment_approved_at_idx`, B-tree em `approved_at` | O intervalo curto de aprovação seleciona poucos pagamentos antes da junção com pedidos | Ocupa espaço e é mantido na inclusão/alteração do pagamento simulado |
| `order_pending_created_idx`, B-tree em `(created_at, id)` onde `status='PENDING_PAYMENT'` | Percorre somente os pendentes, já na ordem de criação e com desempate por ID; permite parar em 20 registros | Novos pendentes entram; pagamento/cancelamento os retiram; depende de a consulta implicar o predicado |

O predicado parcial é fixo; não usa `now()` nem expiração. O filtro de idade continua na consulta. Uma ordenação diferente ou uma busca sem o estado pendente pode não aproveitar esse índice. O planejador escolhe os acessos; o experimento não desativa `enable_seqscan` nem força o uso dos candidatos.

A migration é uma `AddIndex` comum e reversível, adequada ao ambiente local desta entrega. A construção adquire bloqueios e pode interferir em escritas; não foi validada uma operação sem interrupção em produção. O tempo de construção e o espaço são medidos. O custo de escrita e a latência sob concorrência não foram medidos, portanto não atribuo números a eles.

## Resultados medidos

A execução final de **24/10/2026** está preservada no [JSON com todos os planos e amostras](etapa-09-planos.json). Os filtros, parâmetros, sete hashes de resultado e definições dos índices também constam desse arquivo. Foram medidas **245 execuções**, além de 70 aquecimentos, em cinco fases.

| Registros | Quantidade |
| --- | ---: |
| `accounts.User` | 501 |
| `accounts.Customer` | 500 |
| `catalog.Product` | 1.000 |
| `inventory.Stock` | 1.000 |
| `orders.Order` | 20.000 |
| `orders.OrderItem` | 40.094 |
| `orders.SimulatedPayment` | 18.000 |
| `orders.Shipment` | 12.000 |
| `inventory.StockMovement` | 43.024 |

Estados: 1.000 pendentes, 6.000 pagos, 5.000 enviados, 7.000 entregues e 1.000 cancelados. Todos os 18.000 pagamentos são simulados. A auditoria retornou **zero violações nos sete grupos de invariantes**.

A criação varia de 01/01/2024 00:53 UTC a 31/12/2025 23:51 UTC. Dezembro de 2025 contém **6.684 pedidos (33,42%)**; o cliente de ID fictício 1 tem **4.018 pedidos (20,09%)**. O produto fictício 1 aparece em **7.009 pedidos (35,045%)**. As quantidades 1–5 aparecem em 8.015, 8.099, 7.887, 8.012 e 8.081 itens, respectivamente. Há 100 produtos inativos. A distribuição mensal completa está no JSON.

Configuração observada: `shared_buffers=128MB`, `work_mem=4MB`, `effective_cache_size=4GB`, `random_page_cost=4`, `max_parallel_workers_per_gather=2`, `jit=on`, `enable_seqscan=on`. As versões completas constam da evidência.

### Tempos de execução

Valores em milissegundos. Cada célula mostra a **mediana** de sete amostras.

| Consulta | Sem candidatos | Só pagamento | Ambos | Só pendências | Sem candidatos novamente |
| --- | ---: | ---: | ---: | ---: | ---: |
| 20 pendências mais antigas | 0.939 | 0.919 | 0.013 | 0.012 | 0.924 |
| Faturamento de um dia | 0.576 | 0.039 | 0.037 | 0.599 | 0.574 |
| Faturamento anual | 7.956 | 8.114 | 8.039 | 8.186 | 8.156 |
| Top 20 produtos de um dia | 0.627 | 0.103 | 0.101 | 0.661 | 0.632 |
| 20 pedidos de um cliente | 0.027 | 0.027 | 0.026 | 0.025 | 0.026 |
| Pedido por PK | 0.004 | 0.004 | 0.004 | 0.004 | 0.004 |
| 20 produtos com estoque baixo | 0.155 | 0.154 | 0.160 | 0.164 | 0.161 |

Intervalos mínimo–máximo das fases sem candidatos e com ambos:

| Consulta | Sem candidatos (ms) | Ambos (ms) | Buffers hit na raiz, primeira amostra: antes → ambos |
| --- | ---: | ---: | ---: |
| 20 pendências mais antigas | 0.911–0.961 | 0.012–0.018 | 1754 → 22 |
| Faturamento de um dia | 0.558–0.591 | 0.035–0.045 | 429 → 78 |
| Faturamento anual | 7.903–8.190 | 7.950–8.266 | 2126 → 2126 |
| Top 20 produtos de um dia | 0.624–0.652 | 0.097–0.113 | 606 → 255 |
| 20 pedidos de um cliente | 0.026–0.028 | 0.025–0.032 | 38 → 38 |
| Pedido por PK | 0.004–0.005 | 0.004–0.004 | 3 → 3 |
| 20 produtos com estoque baixo | 0.148–0.170 | 0.146–0.178 | 396 → 396 |

Todas as 245 amostras medidas registraram `Shared Read Blocks=0` na raiz. Não houve promessa de acesso a disco físico nem de cache frio.

### Como os planos explicam os resultados

Em `oldest_pending`, o filtro deixa 1.000 dos 20.000 pedidos. Sem candidato, há varredura de toda a tabela e ordenação para obter 20. Com o índice parcial, a leitura já está ordenada e para após os primeiros 20: **0,939 → 0,013 ms**, redução absoluta de **0,926 ms** nesta execução. A fase só com pendências confirma a mudança, e a volta à base sem candidatos retorna a 0,924 ms.

O dia selecionado é **15/10/2025**, entre meias-noites de São Paulo. O B-tree de aprovação permite selecionar poucos pagamentos antes de verificar o estado do pedido pela PK. O faturamento diário passa de **0,576 para 0,037 ms**, redução de **0,539 ms**. O ranking de produtos usa esse mesmo filtro, aproveita os índices existentes de itens e produtos e passa de **0,627 para 0,101 ms**. Não foi preciso acrescentar um novo índice aos itens.

O intervalo anual é **01/01/2025 a 01/01/2026, fim exclusivo**, em São Paulo. A seletividade é baixa: muitas linhas participam. O plano conserva varreduras e hash join, com **7,956 ms antes e 8,039 ms com ambos**, dentro de intervalos que se sobrepõem. **Não houve ganho demonstrável** e o índice de aprovação não foi usado nessa consulta. A última fase sem candidatos chegou a 8,156 ms; a variação não sustenta atribuir pequenas diferenças ao índice. Os planos também estimam 11.682 pagamentos no início e 11.684 com ambos, para os mesmos 11.682 registros reais; essa pequena diferença está preservada nas evidências e não foi ocultada.

A busca por cliente seleciona o cliente do primeiro pedido, não o cliente mais concentrado da carga. O índice já existente na FK atende o filtro; ainda há ordenação e os candidatos não trazem ganho demonstrável. A busca por PK já usa sua chave e fica em 0,004 ms. Estoque baixo faz uma junção de duas tabelas de 1.000 linhas e conserva varreduras sequenciais; não acrescentei um índice especulativo para tentar mudar essa escolha.

Excertos dos planos reais abaixo mostram linhas estimadas e reais por execução do nó; `loops` indica quantas vezes ele foi executado. Os planos completos incluem tempos, filtros, linhas descartadas e buffers de cada nó.

`oldest_pending` / `baseline`, primeira amostra:

```text
Limit (estimadas=20; reais=20; loops=1)
  Sort (estimadas=1000; reais=20; loops=1)
    Seq Scan orders_order (estimadas=1000; reais=1000; loops=1)
```

`oldest_pending` / `both`, primeira amostra:

```text
Limit (estimadas=20; reais=20; loops=1)
  Index Scan orders_order [order_pending_created_idx] (estimadas=1000; reais=20; loops=1)
```

`revenue_day` / `baseline`, primeira amostra:

```text
Aggregate (estimadas=17; reais=1; loops=1)
  Sort (estimadas=17; reais=19; loops=1)
    Nested Loop (estimadas=17; reais=19; loops=1)
      Seq Scan orders_simulatedpayment (estimadas=19; reais=19; loops=1)
      Index Scan orders_order [orders_order_pkey] (estimadas=1; reais=1; loops=19)
```

`revenue_day` / `both`, primeira amostra:

```text
Aggregate (estimadas=17; reais=1; loops=1)
  Sort (estimadas=17; reais=19; loops=1)
    Nested Loop (estimadas=17; reais=19; loops=1)
      Bitmap Heap Scan orders_simulatedpayment (estimadas=19; reais=19; loops=1)
        Bitmap Index Scan [payment_approved_at_idx] (estimadas=19; reais=19; loops=1)
      Index Scan orders_order [orders_order_pkey] (estimadas=1; reais=1; loops=19)
```

`revenue_year` / `baseline`, primeira amostra:

```text
Aggregate (estimadas=10514; reais=365; loops=1)
  Sort (estimadas=10514; reais=11682; loops=1)
    Hash Join (estimadas=10514; reais=11682; loops=1)
      Seq Scan orders_order (estimadas=18000; reais=18000; loops=1)
      Hash (estimadas=11682; reais=11682; loops=1)
        Seq Scan orders_simulatedpayment (estimadas=11682; reais=11682; loops=1)
```

`revenue_year` / `both`, primeira amostra:

```text
Aggregate (estimadas=10516; reais=365; loops=1)
  Sort (estimadas=10516; reais=11682; loops=1)
    Hash Join (estimadas=10516; reais=11682; loops=1)
      Seq Scan orders_order (estimadas=18000; reais=18000; loops=1)
      Hash (estimadas=11684; reais=11682; loops=1)
        Seq Scan orders_simulatedpayment (estimadas=11684; reais=11682; loops=1)
```

### Custo de construção e armazenamento

| Índice | Construção observada (ms) | Espaço observado |
| --- | ---: | ---: |
| `payment_approved_at_idx` | 3.044 | 417.792 bytes (408 KiB) |
| `order_pending_created_idx` | 3.287 | 49.152 bytes (48 KiB) |

O total adicional observado é **466.944 bytes (456 KiB)**. O tempo de construção é uma única observação por índice, inclui a ida ao servidor e a conclusão do comando e não deve ser tratado como previsão para outra base. Os tamanhos dos índices anteriores incluem a história de escrita e reposicionamento desta fixture; `VACUUM` não reconstrói nem compacta automaticamente todos os índices.

O hash integral do domínio permaneceu igual durante as medições. A demonstração pequena, em outro banco, manteve o hash **`013f437a83e0cea887b3cff4ab81939c2fb4b8d5767d6f3068f6067a43df0483`**, com 5 pedidos e saldos 26/17/45. O banco maior foi removido; o arquivo de planos foi preservado.

## N+1 na API

N+1 acontece quando uma lista faz uma consulta inicial e repete consultas para cada registro. Um índice não elimina essas idas ao banco. `select_related()` faz junções para relações unitárias; `prefetch_related()` busca coleções em outra consulta e as associa em memória.

A listagem já tinha o carregamento otimizado desde a Etapa 7. Nesta etapa conferi sua eficácia com 1, 20 e 100 pedidos, comparando o conteúdo completo do serializer simples com o otimizado. Não atribuo uma melhoria nova ao código que já existia.

| Pedidos na página | Serializer simples | Serializer com carregamento otimizado | HTTP com JWT e paginação |
| ---: | ---: | ---: | ---: |
| 1 | 4 consultas | 2 consultas | 4 consultas |
| 20 | 61 consultas | 2 consultas | 4 consultas |
| 100 | 301 consultas | 2 consultas | 4 consultas |

Os conteúdos simples e otimizado foram iguais nas três páginas; seus hashes estão na evidência.

O cenário HTTP usa o JWT somente em memória. A contagem inclui autenticação e paginação; não inclui o pedido adicional de contagem usado pelo próprio experimento para conferir o tamanho da página. Os testes exigem contagens constantes até o tamanho máximo permitido, sem impor limites de tempo ou decisões específicas do planejador em uma base pequena.

## Reproduzir

Na raiz do repositório, com `.env` preparado e Docker em execução:

```bash
docker compose build app
docker compose up -d --wait db
mkdir -p .local/stage9-output
# Diretório reservado a resultados fictícios; o container executa com UID 10001.
chmod 777 .local/stage9-output
docker compose run --rm \
  -v "$PWD/.local/stage9-output:/benchmark-output" \
  --entrypoint python app scripts/benchmark_stage9.py \
  --orders 20000 --customers 500 --products 1000 --seed 42 --repeats 7 \
  --output /benchmark-output/result.json
```

O arquivo de saída deve ser novo. A gravação final usa criação exclusiva (`open("x")`): mesmo que duas execuções passem pela verificação inicial antes de gerar os dados, a segunda escrita falha com `FileExistsError` e preserva a primeira evidência. Nas repetições, escolha outro nome. O diretório de resultados não deve conter `.env` nem outros arquivos privados. A permissão ampla é apenas para esse diretório de dados fictícios, não para o projeto inteiro. No ambiente usado nesta entrega, acrescentei `APP_PORT=18003` e `-p loja-stage3-20261023223148` aos comandos Compose.

Para um ensaio menor, use `--orders 100 --customers 10 --products 20 --repeats 3`. Quantidades aceitas: 1–100000 pedidos, 2–2000 clientes, 10–5000 produtos, 3–30 repetições. A seed aceita inteiros de 0 a 2147483647. Volumes diferentes mudam distribuição, seletividade e planos; não compare seus tempos como se a carga fosse a mesma.

Também é possível executar `python scripts/benchmark_stage9.py ...` em um ambiente virtual com as dependências instaladas e as variáveis `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` e `PGDATABASE` configuradas para um PostgreSQL de desenvolvimento. O script usa `config.settings.test` por padrão; Docker preserva a configuração de desenvolvimento já fornecida pelo Compose.

## Verificação e limites

A suíte completa passou com **248 testes locais e 248 no Docker**, incluindo 20 novos. Verifica isolamento, recusa de base preenchida, rollback completo, repetibilidade dos valores de negócio sem depender das sequências, credenciais fictícias inutilizáveis, detecção de corrupções, conteúdo e número de consultas, presença de métricas reais no plano PostgreSQL e a intercalação de duas escritas no mesmo caminho. Consulte o [parecer aprovado](etapa-09-parecer.md), o [pacote de revisão](etapa-09-revisao.md) e as [evidências finais](etapa-09-evidencias.txt).

O experimento não mede produção, carga concorrente, cache frio, p95/p99 da API, throughput, custo de escrita, milhões de pedidos ou uma combinação arbitrária de filtros. Sete amostras e duas bases sem candidatos ajudam a interpretar variação, mas não constituem um estudo estatístico com intervalos de confiança. Percentuais e razões locais não prometem o mesmo ganho em outro computador ou volume.

Uma interrupção durante a gravação pode deixar um JSON parcial. O comando não publica um marcador de sucesso nesse caso; use somente saídas de execuções concluídas e que possam ser interpretadas como JSON válido. Gravar primeiro em temporário e publicar o resultado completo sem sobrescrita ficou como melhoria opcional da revisão. A proteção contra truncar evidência anterior já está implementada.

A Etapa 10 permanece pendente. Não há deploy da aplicação.

## Referências técnicas

Consultei a documentação primária do PostgreSQL 17: [interpretação de EXPLAIN](https://www.postgresql.org/docs/17/using-explain.html), [índices parciais](https://www.postgresql.org/docs/17/indexes-partial.html) e [índices de múltiplas colunas](https://www.postgresql.org/docs/17/indexes-multicolumn.html). A decisão de manter os candidatos deriva dos planos e medições desta carga, não de uma garantia geral dessas fontes.
