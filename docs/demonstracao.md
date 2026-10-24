# Roteiro de apresentação com curl

Objetivo: demonstrar as regras do domínio e uma melhoria de desempenho já medida, com dados fictícios e **pagamento simulado, sem cobrança real**. A API é o produto deste projeto; não há checkout financeiro nem transportadora externa.

## Preparação

Siga o [guia de execução](execucao.md), preferencialmente usando um projeto/volume novo na porta `18011`. É necessário ter executado `migrate` e `seed_demo` nesse ambiente. O administrador fictício deve usar a senha correspondente ao `.env` local. São necessários Bash, curl 7.82+ e Python 3.9+ com o fuso `America/Sao_Paulo` disponível.

Na raiz do projeto:

```bash
bash examples/demonstracao.sh http://127.0.0.1:18011
```

Para a configuração padrão, use `http://127.0.0.1:8000`. Se a configuração privada estiver em outro arquivo:

```bash
DEMO_ENV_FILE=.local/apresentacao.env bash examples/demonstracao.sh http://127.0.0.1:18011
```

O script lê `.env` como dados e usa apenas `DEMO_PASSWORD`; não executa o arquivo como shell. Antes de escrever no domínio, confere a saúde, autentica o administrador fictício e verifica seu papel. Em seguida cria um cliente, dois produtos de SKU único e dois pedidos. Não apaga registros existentes. Cada execução acrescenta novos registros; o roteiro não é um reset nem uma operação idempotente.

Somente origens HTTP em `127.0.0.1`, `localhost` ou `::1` são aceitas, sem usuário/senha na URL, caminho, query ou fragmento. Não segue redirecionamentos e desabilita proxy e configuração automática do curl. Isso mantém o roteiro restrito à apresentação local, em vez de encaminhar credenciais inadvertidamente para outro destino.

## Como os exemplos usam curl

O [arquivo executável](../examples/demonstracao.sh) contém as chamadas reais. `call_api` é apenas uma função Bash que acrescenta a origem, espera um status e salva a resposta em arquivo temporário privado. Por exemplo, o fluxo chama:

```bash
call_api order POST /api/orders/ 201 customer order
call_api payment POST "/api/orders/$demo_order_id/simulated-payment/" 200 admin empty
call_api cancel POST "/api/orders/$demo_cancel_id/cancel/" 200 customer empty
call_api no-stock POST /api/orders/ 409 customer no-stock
```

Essas linhas pertencem ao script e dependem de suas variáveis/funções; para executar o conjunto, use o comando `bash` acima. O curl recebe o JSON por `--json @arquivo` e a autorização por `--header @arquivo`, sem senha ou token nos argumentos. Seu status é capturado por `--write-out '%{http_code}'`; o corpo não é despejado no terminal.

O pedido de três unidades usa este formato, com ID obtido da criação do produto:

```json
{
  "items": [{"product_id": 4, "quantity": 3}],
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
```

`4` é somente ilustrativo; o script não assume IDs fixos. Dono, preço, total e estado não são enviados pelo cliente. As ações de pagamento, entrega e cancelamento enviam `{}`. O envio acrescenta um `tracking_code` com prefixo `SIMULATED-`.

## Os onze pontos da apresentação

| Passo do PDF | Mostrar e explicar | Resultado conferido pelo roteiro |
| --- | --- | --- |
| 1. Criar cliente | `POST /api/auth/register/`; email único `@example.com`, nome fictício e senha gerada localmente | 201; cliente sem privilégio administrativo |
| 2. Autenticar | `POST /api/auth/token/` para cliente e administrador | 200; tokens usados somente nos arquivos privados da sessão |
| 3. Consultar produtos | O administrador prepara dois produtos próprios; um recebe entrada de 5 unidades e outro permanece com 0. O cliente consulta `/api/products/` | 201 nas criações/entrada e 200 na lista |
| 4. Criar pedido | Cliente compra 3 unidades do produto de `25.90` | 201; pedido pendente de `77.70`, calculado pelo servidor |
| 5. Conferir estoque | Administrador consulta `/api/stock/{product_id}/` antes/depois da criação | 5 → 2; a reserva ocorre na criação |
| 6. Confirmar pagamento simulado | Administrador chama `/simulated-payment/` | 200, `is_simulated=true`, valor `77.70`; sem nova baixa |
| 7. Enviar e entregar | Administrador chama `/ship/` e `/deliver/` | 200, estado final DELIVERED; saldo ainda 2 |
| 8. Cancelamento permitido | Cliente cria outro pedido de 2 unidades; saldo chega a 0. Cancela esse pendente | 201/200; estado CANCELLED; saldo volta a 2 |
| 9. Compra sem estoque | Cliente tenta comprar uma unidade do segundo produto, cujo saldo é 0 | 409 com `insufficient_stock`, sem novo pedido |
| 10. Faturamento | Administrador consulta faturamento e ticket no período atual, com datas de São Paulo | 200 e metadados de simulação; o pagamento do roteiro participa |
| 11. Melhoria medida | Abrir o [relatório de desempenho](etapa-09-desempenho.md) e seus planos | Explicar o índice parcial e a diferença entre resultado seletivo e consulta anual sem ganho |

A autenticação e a preparação administrativas são pré-condições operacionais. A sequência comercial começa no cliente novo. O script faz 24 requisições, pois também lê os saldos intermediários e o perfil administrativo.

## O que dizer sobre integridade

Ao comprar, pedido, itens, estoque e reserva confirmam na mesma transação. A reserva não é um segundo desconto durante o pagamento. O histórico de preço/endereço é próprio do pedido. Ao cancelar, o serviço devolve a reserva e registra uma liberação; pagamentos/envios/entregas seguem o estado permitido.

Para explicar a última unidade e pagamento versus cancelamento concorrentes, abra a [arquitetura](arquitetura.md) e a [matriz de testes](etapa-10-testes-ci.md). O roteiro curl é sequencial e **não é a evidência de concorrência**. Essa evidência vem dos testes PostgreSQL com PIDs distintos e bloqueio observado.

## O que dizer sobre desempenho

Na carga separada da Etapa 9, havia 20 mil pedidos, 500 clientes e mil produtos. Para as 20 pendências mais antigas, a mediana passou de **0,939 para 0,013 ms**, com buffers hit na raiz de **1.754 para 22**, após o índice parcial `(created_at, id)` de pendentes. O índice permite percorrer registros já ordenados e parar após 20, em vez de varrer e ordenar a tabela inteira.

Faturamento de um dia passou de **0,576 para 0,037 ms** com índice na aprovação do pagamento. O relatório anual manteve varreduras e não teve ganho demonstrável. São valores SQL locais, com cache aquecido e sete amostras por fase; não são latência da API ou promessa para produção. Os dois índices ocuparam **456 KiB** nessa carga. O roteiro curl não refaz essa medição nem mede latência.

## Resultado real desta entrega

No ensaio isolado de 24/10/2026, o script concluiu as **24 chamadas** com os status esperados. Os saldos seguiram **5 → 2 → 2 → 0 → 2**, com o outro produto permanecendo em zero. O pedido entregue foi `77.70`; o segundo foi cancelado. Faturamento e ticket do período foram `77.70`, em um pagamento simulado.

A base nova começou com 5 pedidos do gerador e terminou com 7. Ficaram 5 usuários, 4 clientes, 5 produtos, 5 estoques, 9 itens, 4 pagamentos simulados, 3 remessas e 15 movimentos. A auditoria dos sete grupos de invariantes retornou zero violações. Os 251 testes passaram nesse servidor PostgreSQL, e os registros da apresentação permaneceram iguais após a suíte.

Esses totais descrevem aquela execução. Em uma base reutilizada, o faturamento global pode incluir outros pagamentos. O script exige pelo menos o valor do próprio pagamento, sem afirmar que a soma global sempre será exatamente `77.70`. Ele considera o início e fim da execução em São Paulo, inclusive se atravessar meia-noite.

## Arquivos privados e interrupções

O roteiro usa diretório temporário privado, `umask 077` e respostas/headers em arquivos, não em logs. Desativa rastreamento do shell e remove seu diretório ao terminar ou falhar normalmente. Não use modos de rastreamento externos nem compartilhe respostas de login. Tokens não são material de portfólio.

Se um POST confirmar e a etapa seguinte falhar, os registros confirmados permanecem. Não há transação única através de várias chamadas HTTP nem repetição automática de escritas. Uma interrupção forçada pode impedir a limpeza temporária; trate esses arquivos como privados. Use um ambiente novo para repetir a apresentação do zero.

A consulta de faturamento é uma leitura global do período; não cria isolamento financeiro por roteiro. Em tráfego concorrente, chamadas separadas também não compartilham um snapshot global. Consulte [limitações e próximos passos](limites-e-proximos-passos.md).

## Material para abrir durante a apresentação

- [Execução e dados iniciais](execucao.md).
- [ER, estados e decisões transacionais](arquitetura.md).
- [API/OpenAPI](api.md) e [Swagger local da apresentação](http://127.0.0.1:18011/api/docs/).
- [Planos e medições reais](etapa-09-desempenho.md).
- [Cobertura dos riscos e CI](etapa-10-testes-ci.md).

As opções `--json @arquivo` e `--header @arquivo` seguem o [manual oficial do curl](https://curl.se/docs/manpage.html). A versão mínima escolhida para o roteiro é 7.82.0, quando `--json` foi introduzido.
