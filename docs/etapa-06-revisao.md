# Pacote para revisão técnica — Etapa 6

Situação: implementação e validações concluídas; aprovada em revisão técnica independente, sem correções obrigatórias. Consulte o [parecer final](etapa-06-parecer.md). A Etapa 7 não foi iniciada.

## Critérios da revisão técnica

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

PDF: `documento de requisitos fornecido pelo usuario (PDF externo ao repositorio)`, já lido integralmente e relido na Etapa 5. Foram conferidos os requisitos da Etapa 6 e as decisões do domínio antes da implementação. O desenvolvimento adota entregas incrementais e revisão antes de avançar.

Contrato, regras e limites estão em [Etapa 6](etapa-06-transicoes.md). As Etapas 2 a 5 estão aprovadas em seus pareceres.

## Arquivos alterados/adicionados

Caminhos relativos à raiz `loja-pedidos-estoque/`. Não houve alteração de modelos, migrations, dependências ou isolamento de banco. O projeto continua sem commit no repositório pai; não foi enviado ao GitHub ou publicado.

| Arquivo | Mudança |
| --- | --- |
| `orders/lifecycle.py` | Serviços atômicos, autorização, bloqueios, transições e resultados coerentes |
| `orders/integrity.py` | Conferência entre pedido, itens, reservas, liberações, pagamento e entrega |
| `orders/exceptions.py` | Conflito de integridade com diagnóstico interno e mensagem HTTP genérica |
| `orders/validation.py` | Validação direta de rastreamento para chamadas sem HTTP |
| `orders/serializers.py` | Corpos de ação estritos, pagamento simulado, entrega e envelope da resposta |
| `orders/views.py` | Apresentação das quatro ações e conflitos esperados |
| `orders/urls.py` | Quatro rotas de ação |
| `orders/demo_data.py` | Uso dos serviços de transição; somente datas/referências são fixadas pela fixture |
| `tests/order_fixtures.py` | Snapshot dos dados de negócio para conferir ausência de efeitos parciais |
| `tests/concurrency.py` | Helper compartilhado com observação de bloqueio real e ponto de pausa controlado |
| `tests/test_order_concurrency.py` | Usa o helper compartilhado; mantém os sete testes anteriores |
| `tests/test_order_lifecycle.py` | 21 testes de operações, HTTP, permissões, repetição, limites e rollback |
| `tests/test_order_integrity.py` | 10 testes de inconsistências sem reconstrução silenciosa do histórico |
| `tests/test_lifecycle_concurrency.py` | 11 cenários concorrentes com conexões independentes |
| `tests/test_demo_data.py` | Falha no fluxo de envio e snapshot ampliado de reprodutibilidade |
| `README.md` | Situação, ações disponíveis e documentação da entrega |
| `docs/etapa-06-transicoes.md` | Conceitos, regras, contrato, exemplo e limites |
| `docs/etapa-06-revisao.md` | Este pacote |
| `docs/etapa-06-evidencias.txt` | Execuções reais sem segredos/tokens |
| `docs/etapa-06-parecer.md` | Parecer final aprovado, escopo e limites da revisão |

`.env`, `.venv` e `.local` permanecem privados/ignorados. Scripts de coleta específicos deste computador não fazem parte da aplicação.

## Pontos para conferir

1. O pedido é bloqueado antes de conferir estado/histórico; cancelamento filtra pelo dono. Papel atual é consultado também nas chamadas diretas ao serviço.
2. Cancelamento segue pedido → produtos → estoques; os dois últimos grupos são ordenados por produto. Essa ordem inclui as referências usadas pelas FKs das liberações.
3. Pagamento não usa valor enviado e não toca estoque. Envio/entrega preservam reservas. Cancelamento devolve uma vez e não pode ocorrer depois do pagamento.
4. Toda repetição revalida permissões e histórico, preserva datas/referências/estado e não corrige registros ausentes silenciosamente. Envio repetido exige código normalizado igual.
5. Resultado contém objetos capturados na transação para não misturar datas/estado com relacionamentos consultados depois do commit. Itens e endereço continuam imutáveis.
6. Overflow na devolução e estoque ausente causam conflito antes de escrever. Não há truncamento de unidades nem criação automática de estoque.
7. O gerador executa os serviços e só depois ajusta datas/referências fictícias, em base vazia e na mesma transação externa. Testes conferem os valores conhecidos e a reprodutibilidade ampliada.

## Verificações concluídas

- **152 testes locais e 152 no Docker Linux ARM64:** 109 anteriores + 43 novos.
- Checks do Django, Ruff/formatação, dependências, ausência de migrations novas/pendentes e saúde do Compose.
- Onze testes novos de concorrência, mais os sete de criação anteriores, com PIDs distintos e espera observada no PostgreSQL; não são executados apenas em sequência.
- Falha após gravações provoca rollback das quatro transições; cancelamento com rollback concorrente permite que o pagamento aguardando avance sem liberação de estoque.
- HTTP em banco/container temporários: ciclo até entrega, cancelamento de outro pedido pendente, repetições, tentativas indevidas e conciliação dos saldos/movimentos.
- Snapshot principal idêntico antes/depois e remoção somente dos recursos temporários criados pela verificação.

Saídas completas em [evidências](etapa-06-evidencias.txt). Não houve falha de teste nas rodadas direcionadas/finais desta etapa. Os tempos impressos são duração de execução da suíte, sem alegação de desempenho do sistema.

Limites: API completa, consulta/listagem, catálogo, gestão de estoque, OpenAPI e documentação geral permanecem na Etapa 7. O critério de leitura de pedido alheio ainda será verificado nesse endpoint. Não há integração de pagamento real, retry automático, expiração de reservas, validação de produção, outras arquiteturas ou CI nesta entrega.
