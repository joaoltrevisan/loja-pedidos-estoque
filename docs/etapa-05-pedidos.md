# Etapa 5 — Criação de pedidos e reserva de estoque

A entrega implementa o serviço transacional e `POST /api/orders/`. Um cliente cria um pedido para si; o servidor calcula o total, guarda o histórico e reserva todas as unidades solicitadas. **Os pagamentos do projeto são simulados, sem cobrança real.** Criar um pedido não gera pagamento nem entrega.

Essa rota mínima permite verificar a criação e suas permissões agora. Listagem/detalhe, filtros, paginação e OpenAPI continuam na Etapa 7; cancelamento, pagamento simulado, envio e entrega continuam na Etapa 6. Essas operações não foram antecipadas.

## O que uma transação protege

Imagine um pedido com dois produtos. Sem uma transação, uma falha poderia deixar o primeiro estoque reduzido e nenhum pedido completo. `transaction.atomic()` reúne pedido, itens, saldos e movimentos: todos persistem, ou todos voltam ao estado anterior.

Uma transação sozinha não impede duas compras de lerem o mesmo saldo. O bloqueio de linha com `select_for_update()` faz uma compra esperar quando outra mantém o produto ou estoque bloqueado. Depois da espera, a segunda confere o saldo que realmente restou. Se só havia uma unidade, apenas uma compra é confirmada; a outra recebe indisponibilidade.

O fluxo em `orders/services.py` é:

1. Consultar o papel atual do usuário. Exigir conta ativa, perfil de cliente e ausência de papel administrativo, inclusive para chamadas diretas ao serviço.
2. Validar formato, limites, produtos repetidos e endereço, sem consultar disponibilidade fora da transação.
3. Abrir a transação; bloquear todos os produtos por ID crescente e conferir existência/atividade.
4. Bloquear todos os estoques por ID crescente de produto e conferir presença e disponibilidade.
5. Ler os preços dos produtos bloqueados e somar com `Decimal`.
6. Criar pedido `PENDING_PAYMENT`, endereço e itens com preço, SKU e nome históricos.
7. Reduzir cada saldo e registrar uma `RESERVATION` negativa por produto, com pedido, cliente responsável, data e justificativa.
8. Encerrar a transação. Uma exceção em qualquer gravação desfaz todas essas alterações; dentro de uma transação externa, a confirmação definitiva depende também dela.

Regras de negócio e gravações ficam no serviço; validação reutilizável fica em `orders/validation.py`; serializers definem a apresentação; a view aplica autenticação/permissão, chama o serviço e apresenta HTTP. A mesma validação de entrada também protege chamadas sem HTTP. Modelos, migrations e dependências não mudaram.

## Contrato da criação

Somente `items` e `shipping_address` são aceitos no objeto JSON principal. A rota exige `Authorization: Bearer <access>` de um cliente. O dono é obtido do usuário autenticado; não existe parâmetro para escolher outro cliente.

| Entrada | Regra |
| --- | --- |
| `items` | Lista com 1 a 100 itens; um produto por item, sem repetições |
| `items[].product_id` | Inteiro JSON positivo, até 9223372036854775807; produto deve existir e estar ativo |
| `items[].quantity` | Inteiro JSON de 1 a 9999; não aceita booleano, fração, `1.0` nem string `"1"` |
| `shipping_address.recipient` | Texto obrigatório, até 150 caracteres |
| `shipping_address.street` | Texto obrigatório, até 200 caracteres |
| `shipping_address.number` | Texto obrigatório, até 20 caracteres |
| `shipping_address.complement` | Texto opcional, até 100 caracteres; padrão vazio |
| `shipping_address.district` | Texto obrigatório, até 100 caracteres |
| `shipping_address.city` | Texto obrigatório, até 100 caracteres |
| `shipping_address.state` | UF brasileira em maiúsculas |
| `shipping_address.postal_code` | Texto com exatamente oito dígitos ASCII, sem hífen |

Caracteres nulos e strings Unicode inválidas são rejeitados antes de gravar no PostgreSQL. Os textos do endereço perdem espaços nas bordas; os obrigatórios não podem ficar vazios. Comprimentos, UF e CEP reutilizam os validadores dos modelos. O país é definido pelo servidor como `BR`, e a moeda como `BRL`; esses campos não são recebidos na criação.

Campos desconhecidos/protegidos são rejeitados no objeto principal, em cada item e no endereço. Isso inclui dono, preço, total, status, datas, privilégios e dados históricos de produto. Não basta ignorar o preço enviado: a rejeição deixa claro que ele não participa do contrato.

Um produto sem registro de estoque causa conflito `stock_unavailable`; o serviço não inventa um saldo nem cria estoque silenciosamente. A inicialização/gestão de estoque pertence ao fluxo administrativo posterior.

| Resultado | HTTP e comportamento |
| --- | --- |
| Criação válida | 201; pedido, itens e reserva persistidos juntos |
| Formato inválido, limite excedido, duplicação, campo proibido ou produto inexistente | 400; nenhuma alteração |
| Sem autenticação ou JWT inválido | 401 |
| Administrador ou conta sem perfil de cliente | 403 |
| Produto inativo | 409, `code: product_inactive` |
| Estoque não inicializado | 409, `code: stock_unavailable` |
| Saldo insuficiente | 409, `code: insufficient_stock` |
| Outro método na coleção | 405; consulta/detalhe ainda não foram implementados |
| Conteúdo diferente de JSON | 415 |

Respostas tratadas pela rota usam `Cache-Control: no-store`, pois incluem endereço. Erros inesperados de banco não são convertidos em “estoque insuficiente”; a transação é desfeita e o erro segue o tratamento de falha do framework. A padronização completa dos erros e os limites adicionais de API continuam previstos na Etapa 7.

O retorno contém `id`, `customer_id`, `status`, `currency`, `total`, `shipping_address`, `items`, datas e `payment_mode: SIMULATED_NO_REAL_CHARGE`. Cada item retorna produto, quantidade, `unit_price`, SKU/nome históricos e subtotal. Dinheiro é apresentado como string decimal com duas casas, por exemplo `"77.70"`. A criação não preenche datas de pagamento, cancelamento, envio ou entrega.

## Exemplo de uso local

Faça login conforme a Etapa 4. Para descobrir o ID de um produto ativo no ambiente local, enquanto o endpoint de catálogo ainda não existe:

```bash
docker compose exec app python manage.py shell -c "from catalog.models import Product; print(list(Product.objects.filter(is_active=True).values('id', 'sku', 'price', 'stock__available_quantity')))"
```

O exemplo abaixo usa ID ilustrativo `1`; substitua pelo produto escolhido e pelo token de cliente. O Compose padrão atende em 8000. Neste computador, o ambiente já preparado usa 18003 e o projeto `loja-stage3-20261023223148`. Para esse ambiente, use `APP_PORT=18003 docker compose -p loja-stage3-20261023223148` no lugar de `docker compose` nos comandos Docker.

```bash
curl --request POST http://127.0.0.1:18003/api/orders/ \
  --header 'Content-Type: application/json' \
  --header 'Authorization: Bearer SEU_ACCESS_TOKEN' \
  --data-binary @- <<'JSON'
{
  "items": [{"product_id": 1, "quantity": 3}],
  "shipping_address": {
    "recipient": "Cliente Ficticio",
    "street": "Rua Imaginaria",
    "number": "123",
    "district": "Bairro Modelo",
    "city": "Sao Paulo",
    "state": "SP",
    "postal_code": "01001000"
  }
}
JSON
```

Com o caderno fictício a `25.90`, o total é `77.70`. No dataset recém-gerado, seu disponível começa em 26 após os pedidos de demonstração e passa a 23 com essa compra. Esse cenário foi executado por HTTP em um banco temporário; o dataset principal deste computador foi preservado. Reproduzir a compra no seu banco reduz o saldo e cria um novo pedido.

## Preço histórico e alterações simultâneas

Bloquear somente o estoque não estabilizaria preço, nome, SKU e atividade do produto. A criação bloqueia o produto antes de ler esses valores. A futura alteração administrativa deve usar o mesmo protocolo: produtos primeiro, estoques depois, cada grupo ordenado por ID de produto.

Se a compra bloquear primeiro, guarda o preço anterior e a alteração espera. Se a alteração confirmar primeiro, a compra espera e usa o novo preço. Se uma inativação confirmar primeiro, a compra é rejeitada. O preço visto antes no catálogo não garante o preço final da compra. Nenhuma alteração posterior reescreve os itens históricos.

Os testes simulam a escrita administrativa em transações controladas; não representam um endpoint administrativo já entregue. Os dois sentidos da disputa de preço e a inativação concorrente foram verificados no PostgreSQL.

## Ordem dos bloqueios e limite da garantia

Um pedido novo bloqueia **produtos em ordem crescente de ID → estoques em ordem crescente de produto**. Para operações futuras sobre pedido existente, o contrato completo permanece **pedido → produtos → estoques**, conforme a Etapa 1. Cancelamento e ajustes precisarão seguir esse contrato mesmo quando seu efeito principal for apenas no saldo.

Uma chave estrangeira também pode exigir bloqueios para proteger uma referência. Na primeira rodada de testes, um cenário artificial bloqueou estoque e depois inseriu uma movimentação que precisava referenciar o produto, na ordem inversa ao contrato. Uma compra segurava o produto e esperava o estoque; o outro lado precisava do produto para confirmar. O PostgreSQL detectou um deadlock. Esse cenário foi corrigido: a sonda de estoque agora mantém apenas o bloqueio, sem gravar referências na ordem inversa, e confere no banco que a compra espera ainda no `SELECT ... FOR UPDATE`.

A ordem consistente reduz risco; não é uma promessa de ausência absoluta de deadlocks, nem protege escritores externos que ignorem o protocolo. Não há retry automático nesta etapa. Escritas manuais na demonstração e o gerador de fixtures não são operações administrativas públicas.

## Gerador fictício

`seed_demo` agora chama `create_order` para os cinco pedidos, em vez de repetir a lógica de preço/reserva. Ele preserva os valores conhecidos, os saldos e os estados da Etapa 3. Depois da criação, apenas a fixture fixa datas históricas e monta as transições cujo serviço será entregue na Etapa 6. Não oferece esse atalho pela API.

O helper do gerador relê o estoque do banco, evitando usar um objeto `product.stock` em cache que possa ter ficado desatualizado após a criação transacional. O teste dos valores conhecidos confere o resultado, e um teste novo provoca falha após dois pedidos para verificar o rollback de todo o dataset. Nenhuma geração foi repetida sobre o volume principal já preenchido.

## Verificações e limites

São **30 testes novos**: 22 de criação/HTTP/entrada/integridade, 7 de concorrência e 1 do gerador. Com os 79 anteriores, a suíte tem **109 testes**. A rodada final passou no PostgreSQL local e no Docker Linux ARM64; consulte o [registro real](etapa-05-evidencias.txt) e o [pacote de revisão](etapa-05-revisao.md).

Nos testes concorrentes, duas threads usam conexões independentes e PIDs distintos. A primeira transação alcança um ponto controlado e mantém os bloqueios; o teste observa `pg_blocking_pids` indicando que a segunda está esperando antes de liberar a primeira. Limites de tempo impedem espera indefinida. Foram verificados:

- Disputa de dois clientes pela última unidade: um confirma, outro recebe indisponibilidade, sem saldo negativo ou reserva extra.
- Pedidos com dois produtos enviados em ordens opostas, com resultado consistente.
- Rollback da primeira compra após gravar a reserva, permitindo que a segunda confirme.
- Alteração de preço antes/depois da compra e inativação antes da compra.
- Espera pelo estoque ainda na leitura bloqueante, antes de gravar a reserva.

O teste de rollback HTTP provoca falha **após** pedido, itens, saldos e movimentos terem sido gravados dentro da transação; o snapshot persistido volta integralmente ao estado anterior. As operações repetidas de criação produzem pedidos distintos: esta versão não implementa chave de idempotência para compra. Idempotência de pagamento e cancelamento continua na Etapa 6.

Esses resultados não são medições de desempenho, não comprovam outras arquiteturas nem validam concorrência de pagamento/cancelamento ou envio/entrega. O critério de acesso aos endpoints reais de consulta de pedidos continua pendente para quando esses endpoints existirem. A Etapa 6 não foi iniciada.

Referências oficiais consultadas: [transações no Django 5.2](https://docs.djangoproject.com/en/5.2/topics/db/transactions/), [select_for_update e TransactionTestCase](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update) e [bloqueios no PostgreSQL 17](https://www.postgresql.org/docs/17/explicit-locking.html). A configuração mantém o isolamento padrão READ COMMITTED do PostgreSQL; a correção não depende de trocar silenciosamente para SERIALIZABLE.
