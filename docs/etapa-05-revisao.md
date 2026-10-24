# Pacote para revisão técnica — Etapa 5

Situação: **implementada, validada e aprovada em revisão técnica independente**, sem bloqueadores. Consulte o [parecer final](etapa-05-parecer.md). A Etapa 6 não foi iniciada.

## Critérios da revisão técnica

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

PDF completo: `documento de requisitos fornecido pelo usuario (PDF externo ao repositorio)`. Foi relido integralmente nesta entrega. O usuário controla a sequência incremental e exige a revisão antes da etapa seguinte. O escopo está na [explicação da Etapa 5](etapa-05-pedidos.md); as decisões anteriores estão no domínio e nos pareceres das Etapas 2 a 4.

## Arquivos alterados/adicionados

Caminhos relativos à raiz `loja-pedidos-estoque/`. O projeto continua sem commit no repositório pai; não houve envio ao GitHub, publicação ou deploy.

| Arquivo | Mudança |
| --- | --- |
| `orders/validation.py` | Formato estrito, limites e endereço, sem consultas de disponibilidade |
| `orders/exceptions.py` | Conflitos de disponibilidade esperados, separados de falhas inesperadas |
| `orders/services.py` | Criação, autorização, cálculo, bloqueios, histórico e reserva atômica |
| `orders/serializers.py` | Entrada com campos permitidos e saída histórica/monetária explícita |
| `orders/views.py` | Endpoint de criação e apresentação dos conflitos |
| `orders/urls.py` | Rota somente de criação |
| `config/urls.py` | Inclusão de `/api/orders/` |
| `common/views.py` | Mixin de resposta privada compartilhado |
| `accounts/views.py` | Importa o mesmo mixin movido para common, sem alterar o contrato de autenticação |
| `orders/demo_data.py` | Reutiliza criação transacional; relê estoque sem cache obsoleto; mantém fixture dos estados futuros |
| `tests/order_fixtures.py` | Cenários fictícios com saldo e movimentos reconciliados |
| `tests/test_order_creation.py` | 22 testes de criação, rejeição de adulteração, integridade e rollback |
| `tests/test_order_concurrency.py` | 7 testes com conexões independentes e observação real de espera por bloqueio |
| `tests/test_demo_data.py` | Teste adicional de rollback do dataset após dois pedidos criados pelo serviço |
| `README.md` | Entrega e rota de criação disponíveis |
| `docs/etapa-05-pedidos.md` | Contrato, conceitos, decisões, exemplo e limites |
| `docs/etapa-05-revisao.md` | Este inventário e instrução de revisão |
| `docs/etapa-05-evidencias.txt` | Registros reais de testes, checks e HTTP, sem tokens/segredos |
| `docs/etapa-05-parecer.md` | Parecer final aprovado e limites da revisão |

Não houve mudança de modelos, migrations, esquema, dependências ou configuração de isolamento. `.env`, `.venv` e `.local` permanecem privados/ignorados. Os scripts locais de coleta não fazem parte do código da aplicação.

## Decisões para conferir

1. Serviço recarrega o papel atual do ator e obtém seu `Customer`; não aceita dono, preço, total, status ou datas. Validadores são chamados também no uso direto, sem HTTP.
2. Transação bloqueia produtos ordenados por ID e depois estoques ordenados por produto. Preço, atividade, SKU e nome são lidos sob o bloqueio do produto.
3. Nenhuma escrita precede a validação de todos os produtos/estoques. Pedido, itens, saldos e movimentos participam da mesma transação; valores monetários usam Decimal.
4. Acesso administrativo não permite comprar como cliente nesta versão. Não há GET/detalhe/mutação de pedido existente ainda. A integração de permissões será completada nos endpoints correspondentes.
5. Endpoint de criação foi exposto agora para validar a entrega e a proteção de campos. A API completa e OpenAPI continuam na Etapa 7; fluxos de pagamento simulado/cancelamento/entrega permanecem na Etapa 6.
6. Repetir criação gera um novo pedido; não há idempotência prometida para essa ação. Não há expiração automática de reserva.
7. O gerador chama o serviço de criação, mas ainda monta os estados de fixture para os serviços futuros, com datas fixas. Seus testes de consistência e reprodutibilidade continuam obrigatórios.

## Verificações

**109 testes**: 79 anteriores e 30 novos. A execução final local e Docker, checks, dependências e ausência de migrations novas/pendentes estão em [evidências](etapa-05-evidencias.txt).

Testes de concorrência verificam PIDs distintos e a espera da segunda conexão em `pg_blocking_pids` antes de liberar a primeira. A sonda exclusiva do estoque também confere em `pg_stat_activity` que a espera ocorre no SELECT bloqueante. Não são testes sequenciais nem uma promessa de ausência absoluta de deadlocks.

Uma rodada inicial de 37 testes registrou um erro: um cenário de teste tomava estoque antes de precisar do produto por FK, contrariando a ordem do protocolo. A sonda foi corrigida e a suíte repetida; o caso e a implicação para os futuros serviços estão documentados. A ocorrência inicial não é apresentada como teste aprovado.

O HTTP real usa banco e container temporários, com migrations e seed em base nova: login de cliente/admin, recusas de acesso/adulteração/estoque insuficiente e compra válida. Confere total `77.70`, saldo do caderno de 26 para 23, uma reserva `-3` e ausência de pagamento/entrega novos. O banco/container exclusivos são removidos ao final; o snapshot das nove entidades da demonstração principal é comparado antes/depois para preservar seus dados.

Não há medição de desempenho, validação de produção, outras arquiteturas ou teste de concorrência dos fluxos da Etapa 6 nesta entrega.
