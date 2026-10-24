# Etapa 7 — API e documentação

Implementação da API operacional com catálogo, estoque, auditoria e consulta de pedidos. Pagamentos continuam **SIMULADOS, SEM COBRANÇA REAL**. Dados de demonstração são fictícios.

## Dependência corrigida antes da implementação

O PDF pede endpoints de relatórios na Etapa 7, mas define suas consultas e critérios na Etapa 8. A correção adotada é entregar a API operacional nesta etapa e acrescentar os endpoints e o contrato OpenAPI dos relatórios na Etapa 8, após verificar os cálculos. Não há endpoints de relatório com resultados inventados ou respostas provisórias. Assim, o item de relatórios da API permanece pendente até a próxima entrega, e não se declara a API final completa.

O requisito de autorização das consultas de pedidos, dependente dos endpoints desde a Etapa 4, agora é verificado nas rotas reais: um cliente não lista nem consulta pedidos alheios.

## Executar pela documentação

Prepare o ambiente pelo README. Na execução padrão, abra `http://127.0.0.1:8000/api/docs/`. O ambiente de demonstração já existente neste computador usa a porta `18003`. Não há serviço de aplicação hospedado publicamente.

1. Abra `POST /api/auth/token/`, clique **Try it out** e use o email fictício e a senha local `DEMO_PASSWORD` do seu `.env`.
2. Copie apenas `access`, clique **Authorize** e cole o token. O Swagger acrescenta `Bearer`; não cole a palavra junto do token.
3. Como cliente, consulte `GET /api/products/`, crie um pedido e consulte seu resultado em `GET /api/orders/{order_id}/`.
4. Como administrador, use outra autenticação para consultar estoque e confirmar pagamento simulado, envio e entrega.
5. Como cliente, crie outro pedido pendente e cancele-o. Confira a devolução do saldo com o administrador.

Não compartilhe respostas de login nem capturas com tokens. O Swagger não persiste a autorização entre sessões e não envia o esquema a um validador externo. Seus arquivos JavaScript/CSS vêm do pacote local, sem CDN. A documentação HTML é a interface técnica prevista no PDF; a loja continua sem interface de compras.

O [OpenAPI exportado](openapi.yaml) é validado e corresponde às rotas implementadas. Cada operação registra objetivo, perfil, campos, limites, exemplos ilustrativos e erros. Esses exemplos são documentação, não resultados de execução.

## Rotas e responsabilidades

| Rota | Métodos | Perfil e efeito |
| --- | --- | --- |
| `/api/auth/register/` | POST | Público; cria somente cliente |
| `/api/auth/token/` | POST | Público; login JWT |
| `/api/auth/token/refresh/` | POST | Portador do refresh; novo access |
| `/api/auth/me/` | GET, PATCH | Usuário autenticado; próprios dados |
| `/api/products/` | GET, POST | Cliente consulta ativos; administrador consulta todos e cria |
| `/api/products/{product_id}/` | GET, PATCH | Cliente consulta ativo; administrador atualiza/inativa |
| `/api/stock/` | GET | Administrador consulta saldos |
| `/api/stock/{product_id}/` | GET | Administrador consulta saldo do produto |
| `/api/stock/{product_id}/movements/` | POST | Administrador registra entrada/ajuste |
| `/api/stock/movements/` | GET | Administrador audita movimentos |
| `/api/orders/` | GET, POST | Cliente consulta próprios/cria; administrador consulta todos |
| `/api/orders/{order_id}/` | GET | Cliente consulta próprio; administrador consulta qualquer |
| `/api/orders/{order_id}/simulated-payment/` | POST | Administrador aprova pagamento simulado |
| `/api/orders/{order_id}/cancel/` | POST | Cliente cancela próprio pendente |
| `/api/orders/{order_id}/ship/` | POST | Administrador envia pago |
| `/api/orders/{order_id}/deliver/` | POST | Administrador entrega enviado |
| `/api/schema/` | GET | Público; contrato OpenAPI, JSON com `?format=json` |
| `/api/docs/` | GET | Público; Swagger UI |

Não se oferece exclusão física de produto nem escrita direta em pedido, pagamento, entrega ou saldo. Para retirar um produto de novas compras, use `PATCH` com `is_active=false`; os pedidos antigos preservam SKU, nome e preço históricos.

## Catálogo e estoque

Criar produto e inicializar seu estoque em zero são uma única transação. Um produto novo ainda não tem movimentos, portanto saldo zero coincide com a soma vazia. A descrição admite até 5000 caracteres; SKU até 64 no formato já definido; nome até 200. Preço entra como texto decimal positivo de até oito dígitos inteiros e duas casas. `is_active` exige booleano JSON.

Uma entrada usa `movement_type=ENTRY` e delta positivo. Um ajuste usa `ADJUSTMENT` e delta positivo ou negativo, nunca zero. Ambos exigem justificativa não vazia de até 500 caracteres. Responsável, data e produto do movimento vêm da autenticação, relógio e URL; o cliente não pode substituí-los.

O saldo resultante deve ficar entre zero e 2147483647. Saldo e movimento confirmam ou voltam juntos. Um ajuste corrige disponibilidade, não altera reservas nem reescreve movimentos anteriores. Administradores podem ajustar estoque de um produto inativo, preservando a auditoria; clientes continuam sem poder comprá-lo. Estoque ausente gera conflito, sem criação ou reparo silencioso.

**Repetir a criação de produto com o mesmo SKU retorna 409. Repetir o POST de movimento cria um novo movimento.** Não há chave de idempotência para entradas, ajustes ou criação de pedido. Em falha de rede após o envio, consulte a auditoria antes de repetir. As garantias de repetição das ações de estado da Etapa 6 continuam válidas.

## Concorrência e preços

A ordem compartilhada dos bloqueios é pedido existente, quando aplicável, produtos por ID e estoques por produto. Atualizar preço ou atividade bloqueia o produto. Entradas/ajustes bloqueiam primeiro o produto e depois o estoque, como compras e cancelamentos.

Isso faz uma compra aguardar uma atualização já em andamento e usar seu preço/atividade confirmados. Se a compra adquirir o bloqueio primeiro, mantém o valor antigo no histórico e a atualização espera. Dois ajustes concorrentes reconsultam o saldo após a espera e não sobrescrevem o resultado um do outro. A ordem reduz risco de deadlock; não se promete que elimine qualquer possibilidade.

## Paginação, filtros e ordenação

As listas respondem com `count`, `next`, `previous` e `results`. O tamanho padrão é 20 e `page_size` aceita de 1 a 100. Página inexistente retorna 404. A ordenação sempre tem desempate por identificador, para tornar previsível a ordem quando valores coincidirem. Mudanças nos dados entre páginas ainda podem deslocar resultados, como em qualquer paginação por número.

| Lista | Filtros | Campos de `ordering` |
| --- | --- | --- |
| Produtos | `search` (nome/SKU, até 200), `sku` exato, `is_active` só admin (`true`/`false`) | `id`, `sku`, `name`, `price`, `created_at` |
| Saldos | `product_id`, `max_quantity` inclusivo | `id`, `product_id`, `available_quantity`, `updated_at` |
| Movimentos | `product_id`, `order_id`, `movement_type` | `id`, `created_at`, `product_id` |
| Pedidos | `status`, `customer_id` só admin, `created_from`, `created_before` | `id`, `created_at`, `total`, `status` |

Use `-` para descendente e vírgulas para até três campos. Campos arbitrários, parâmetros desconhecidos, repetidos e valores vazios são rejeitados. Inteiros em parâmetros de query usam somente dígitos ASCII: `page=1.0`, `page_size=1.00`, sinais, espaços e expoentes retornam 400, sem fallback silencioso. Nenhum nome de campo arbitrário é repassado ao ORM. As permissões filtram pedidos antes da busca/listagem; a verificação de objeto reforça o detalhe. Pedido alheio e inexistente retornam a mesma resposta 404.

Datas de filtro são ISO 8601; início inclusivo, fim exclusivo. Se o fuso for omitido, aplica-se `America/Sao_Paulo`. O fim deve ser posterior ao início. Esses filtros usam criação do pedido; o futuro faturamento usará aprovação do pagamento, conforme a Etapa 8.

## Erros e alteração de contrato

As respostas tratadas pela API agora usam o mesmo envelope:

```json
{
  "code": "validation_error",
  "detail": "Revise os campos informados.",
  "errors": {"price": ["Informe dinheiro como texto decimal, por exemplo 25.90."]}
}
```

`errors` contém erros por campo (inclusive estruturas aninhadas) em validações; nos demais casos é `null`. Isso substitui os erros por campo diretamente na raiz das entregas anteriores. Os testes dessas entregas foram adaptados para `errors`; a verificação da regra foi mantida.

400 indica entrada inválida; 401 credencial ausente/inválida; 403 perfil sem acesso; 404 registro invisível/inexistente ou página ausente; 405 método sem implementação; 409 conflito de estado, SKU, integridade ou saldo; 415 corpo fora de JSON; 429 limite das rotas de autenticação/perfil. Criações retornam 201, consultas/atualizações/ações de estado retornam 200. Detalhes internos de banco ou integridade não vão à resposta. Falhas inesperadas não são convertidas em sucesso.

Respostas de dados e autenticação mantêm `Cache-Control: no-store`. OpenAPI e Swagger são públicos, pois contêm contrato e exemplos fictícios, não registros da loja.

## Dependências verificadas

Adicionadas versões estáveis fixadas: `drf-spectacular 0.30.0` e `drf-spectacular-sidecar 2026.10.1`. Foram consultados os metadados oficiais do [PyPI](https://pypi.org/project/drf-spectacular/) e a [documentação oficial](https://drf-spectacular.readthedocs.io/en/stable/faq.html). Dependências transitivas estão em `requirements.lock`.

Os metadados aceitam o Django/DRF usados; a lista descritiva de versões do projeto cita DRF até 3.17 e não afirma validar 3.18. Por isso, a compatibilidade nesta combinação foi verificada na aplicação com geração/validação do esquema, renderização dos assets e testes locais/Docker. Isso não equivale a uma declaração de suporte do mantenedor. As dependências anteriores foram preservadas.

## Verificação desta entrega

Foram adicionados **39 testes**: 17 de catálogo/estoque, 13 de consulta/documentação e 9 de concorrência. Os **191 testes** completos passaram no PostgreSQL local e no Docker Linux ARM64. Os cenários concorrentes usam conexões independentes e observam bloqueio real no PostgreSQL.

Verificações incluem papéis atuais, pedido alheio, limites, erros, preço histórico, paginação, ordenação permitida, inicialização atômica de estoque, rollback após gravar movimento, concorrência e OpenAPI. A consulta de pedidos foi conferida com 2 e 7 registros: a quantidade de consultas não cresceu por pedido; isso é um teste de regressão de N+1, não uma medição de desempenho.

No ensaio HTTP isolado: produto novo começou em zero; entrada +10; compra de 3 a 12.90 totalizou 38.70; mudança para 15.00 preservou o pedido; pagamento simulado/envio/entrega não alteraram novamente o saldo; outra compra de 2 foi cancelada; ajuste -2 deixou saldo 5, igual à soma dos cinco movimentos. A demonstração principal ficou idêntica antes/depois e o banco/container temporários foram removidos.

O Swagger foi aberto e conferido visualmente em navegador, sem autenticação ou dados pessoais na captura. Consulte [evidências](etapa-07-evidencias.txt) e [pacote de revisão](etapa-07-revisao.md). A Etapa 8 não foi iniciada. GitHub Actions, consultas de negócio e avaliação de índices permanecem nas etapas previstas.
