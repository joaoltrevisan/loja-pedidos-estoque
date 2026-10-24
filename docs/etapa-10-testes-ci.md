# Etapa 10 — cobertura dos riscos e integração contínua

Situação: implementada, verificada e aprovada em revisão técnica, com execução hospedada aprovada no commit de implementação. A Etapa 11 não foi iniciada.

## Por que esta etapa reutiliza testes anteriores

Escrevi os testes junto com cada funcionalidade. Os 15 riscos pedidos nas páginas 6–7 do PDF já tinham casos concretos ao chegar à Etapa 10. Mantive esses testes e acrescentei três cenários pela API, para conferir a integração entre JWT, permissões, tratamento HTTP e transações durante uma disputa real por bloqueio.

A suíte passa de **248 para 251 testes**. Esse número é a quantidade de casos executados, não uma porcentagem de cobertura de linhas ou prova de ausência de erros. Pagamentos, contas, endereços e produtos dos testes são fictícios; não há cobrança real.

## Matriz dos requisitos do PDF

Os métodos abaixo podem ser executados individualmente com `python manage.py test tests.<modulo>.<classe>.<metodo>`. Todos também pertencem à suíte completa, sem seleção que exclua concorrência.

| Risco exigido | Arquivo e métodos representativos | O que o teste confere |
| --- | --- | --- |
| Quantidade zero, negativa ou fracionária | `test_order_creation.py`: `test_input_shapes_empty_repeated_and_quantity_types_leave_no_changes`; `test_schema.py`: testes de `StrictIntegerTests` | Rejeição antes de reserva, sem truncar números fracionários ou aceitar booleanos |
| Produto inexistente ou inativo | `test_order_creation.py`: `test_missing_products_in_multi_item_purchase_never_reserve_partially`, `test_inactive_product_rejects_entire_purchase` | Nenhuma reserva parcial, mesmo em pedido com outro produto válido |
| Estoque insuficiente | `test_order_creation.py`: `test_insufficient_stock_rejects_entire_purchase` | Conflito e domínio inalterado |
| Preço ou total adulterado | `test_order_creation.py`: `test_rejects_owner_price_total_status_and_privileges`, `test_rejects_protected_item_fields` | Cliente não define preço, dono, estado ou total; servidor calcula valores |
| Acesso a pedido de outro cliente | `test_api_read_docs.py`: `test_customer_list_and_detail_are_scoped_before_lookup`; `test_order_lifecycle.py`: `test_role_and_ownership_authorization_apply_to_actual_endpoints` | Lista restrita e detalhe alheio indistinguível de inexistente; ações também verificam dono/papel |
| Obter permissão administrativa | `test_authentication.py`: `test_register_rejects_privilege_and_other_protected_fields`, `test_profile_forbids_mass_assignment_and_password_changes`; `test_permissions.py`: `test_admin_privilege_removal_takes_effect_with_existing_token` | Cadastro/perfil não elevam privilégio e um token antigo não conserva papel removido |
| Falha após alterar estoque | `test_order_creation.py`: `test_failure_after_all_writes_rolls_back_order_items_balances_and_ledger`; `test_order_concurrency.py`: `test_rollback_releases_locks_and_waiting_buyer_can_reserve` | Falha depois das escritas desfaz pedido, itens e razão do estoque; comprador que aguardava pode usar a unidade devolvida pelo rollback |
| Compras simultâneas pela última unidade | `test_order_concurrency.py`: `test_two_customers_dispute_last_unit_and_second_rechecks_after_wait`; novo `test_api_concurrency.py`: `test_http_customers_dispute_last_unit_with_one_created_and_one_conflict` | Uma compra confirma, outra espera bloqueio e rejeita falta de saldo; HTTP 201/409 |
| Pagamento versus cancelamento concorrentes | `test_lifecycle_concurrency.py`: `test_payment_first_prevents_waiting_cancellation`, `test_cancellation_first_prevents_waiting_payment`; novos equivalentes HTTP em `test_api_concurrency.py` | As duas ordens de aquisição do bloqueio terminam em estado/pagamento/saldo coerentes; HTTP 200/409 |
| Cancelamento repetido | `test_order_lifecycle.py`: `test_cancel_returns_stock_records_owner_and_repeats_without_changes`; `test_lifecycle_concurrency.py`: `test_two_cancellations_release_only_once` | Uma única liberação, datas e saldo preservados |
| Pagamento repetido | `test_order_lifecycle.py`: `test_payment_repeat_preserves_reference_dates_and_updated_at`; `test_lifecycle_concurrency.py`: `test_two_payment_confirmations_preserve_one_reference_and_date` | Um único pagamento simulado e referência/data originais |
| Envio antes do pagamento | `test_order_lifecycle.py`: `test_ship_before_payment_and_deliver_before_shipping_are_rejected` | Transição inválida sem escrita parcial |
| Entrega antes do envio | Mesmo teste de transições acima | Transição inválida sem criar datas/remessa indevidas |
| Alterar preço sem reescrever pedidos antigos | `test_order_creation.py`: `test_catalog_changes_do_not_rewrite_old_snapshots`; `test_catalog_stock_concurrency.py`: `test_purchase_first_price_update_preserves_old_snapshot` | Itens/total anteriores preservados; nova compra observa preço confirmado |
| Faturamento e limites de datas | `test_report_selectors.py`: `test_daily_revenue_uses_approval_bounds_and_fills_empty_days`, `test_end_minus_microsecond_is_included_exact_end_is_excluded`, `test_midnight_grouping_uses_sao_paulo_not_utc_or_active_timezone`; `test_report_concurrency.py`: testes de leitura durante pagamento | Aprovação simulada, início inclusivo/fim exclusivo, fuso de São Paulo e leitura coerente do agregado |

Todos esses arquivos estão em `tests/`. As classes principais são `OrderCreationTests`, `OrderConcurrencyTests`, `OrderLifecycleTests`, `LifecycleConcurrencyTests`, `ReadAndDocumentationTests`, `AuthenticationTests`, `ReportSelectorTests` e a nova `APIConcurrencyTests`.

## O que os três testes novos acrescentam

`tests/test_api_concurrency.py` usa `TransactionTestCase` e um `APIClient` diferente por requisição. Não usa `force_authenticate`: envia JWT de acesso fictício ao caminho real da API e percorre autenticação, autorização, serializer, serviço e tratamento de conflito. O cliente de testes executa a aplicação em processo; não há servidor TCP, navegador ou proxy nesse ensaio.

O helper existente `ControlledConcurrencyMixin` cria conexões PostgreSQL independentes, confere PIDs distintos e pausa a primeira operação quando ela já adquiriu o bloqueio. Antes de liberar essa operação, observa `pg_blocking_pids()` e exige que a segunda esteja aguardando a primeira. Não substitui a disputa por duas chamadas sequenciais nem por um `sleep` que presuma a ocorrência do bloqueio. A pequena espera de sondagem apenas consulta o estado real; os timeouts limitam falhas travadas.

No cenário de última unidade, o saldo passa de 1 a 0, há um pedido/um item/uma reserva e a outra requisição recebe `409 insufficient_stock`. Nos cenários de pagamento/cancelamento, a vencedora recebe 200 e a outra `409 invalid_transition`. Se o pagamento venceu, fica PAID, um pagamento simulado, saldo 7 e nenhuma liberação; se o cancelamento venceu, fica CANCELLED, sem pagamento, saldo 10 e uma liberação. Todos conferem razão do estoque e histórico entre tabelas.

Não alterei serviços, modelos, migrations, contratos HTTP ou limites de tempo do helper para fazer a nova suíte passar.

## Workflow

Integração contínua é repetir as verificações automaticamente quando o código é enviado ou proposto em um pull request. O resultado fica associado ao commit executado, permitindo conferir qual versão passou. Aqui o workflow prepara um ambiente novo e reproduz as verificações usadas no desenvolvimento.

Arquivo: `.github/workflows/ci.yml`. O job `Python 3.12 / PostgreSQL 17` roda em `ubuntu-24.04` com Python 3.12.15, dependências de `requirements.lock` e serviço `postgres:17.11-bookworm`. Dispara em `push`, `pull_request` e execução manual. Não há filtro que deixe mudanças de testes/infraestrutura sem verificação.

A ordem é:

1. Obter código e preparar Python.
2. Instalar dependências fixadas.
3. Criar role temporária `loja_ci` e banco de sua propriedade.
4. Executar `pip check`, Ruff e formatação.
5. Verificar Django e ausência de migrations faltantes; aplicar e conferir migrations.
6. Executar toda a suíte no PostgreSQL.
7. Gerar OpenAPI com validação/erro em aviso e comparar com `docs/openapi.yaml`.
8. Executar a inspeção dos arquivos publicáveis.

A role usada pela aplicação tem `LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS`. `CREATEDB` permite ao runner Django criar/remover seu banco de testes; não é recomendação de role de produção. A conta `postgres` serve apenas à preparação desse serviço novo. A suíte existente confere que o backend é PostgreSQL e a conta de testes não é superusuária.

## Segurança e privacidade da CI

O workflow recebe apenas `contents: read`; o checkout não persiste credenciais. As duas Actions oficiais estão fixadas por SHA completo, consultado nos repositórios oficiais em 24/10/2026, em vez de depender de uma tag mutável:

- `actions/checkout` v6: `d23441a48e516b6c34aea4fa41551a30e30af803`.
- `actions/setup-python` v6: `ece7cb06caefa5fff74198d8649806c4678c61a1`.

As senhas `ci-…-not-for-deployment` são valores públicos de teste, exclusivos do serviço temporário. A configuração Django usa sua chave pública exclusiva de testes. Nenhum segredo do `.env`, token pessoal ou conta de demonstração local é fornecido à CI. Não há `pull_request_target`, deploy, publicação de imagem, comentário automático em PR, acesso SSH ou upload do diretório de trabalho como artefato.

O job tem limite de 15 minutos. Uma nova execução da mesma referência cancela a anterior, evitando trabalho obsoleto; cancelamento não é aprovação. O estado dos checks deve ser conferido no commit desejado. O workflow não configura proteção de branch nem bloqueia sozinho um push direto em `main`.

Fixar SHAs e versões reduz mudanças implícitas, mas exige atualização deliberada. O runner Ubuntu e os pacotes obtidos do índice não formam um ambiente integralmente hermético; o lock fixa versões, não hashes de cada distribuição. A CI não executa uma auditoria de vulnerabilidades de dependências nesta entrega.

## Verificações e execução

As verificações locais passaram com **251 testes** no PostgreSQL privado do computador. O ensaio Docker também passou com **251 testes** em outro servidor PostgreSQL, criado exclusivamente para a CI e removido ao terminar. Os comandos de bootstrap, Ruff, migrations, testes e OpenAPI foram lidos do próprio YAML; a rede do ensaio usou o hostname do serviço em vez de loopback. O scanner rodou no host, pois a imagem exclui `.git`; instalação das dependências, checkout e setup-python não foram emulados nesse ensaio.

O `actionlint 1.7.12`, baixado do release oficial e conferido contra o SHA-256 publicado, não apontou erros no workflow. A ausência de saída do lint indica êxito; a evidência registra também seu código de saída. Essa ferramenta foi usada na validação local, sem acrescentar dependência à aplicação.

A demonstração principal preservou o hash de seus nove modelos: `013f437a83e0cea887b3cff4ab81939c2fb4b8d5767d6f3068f6067a43df0483`. Não foi reutilizada como base dos testes ou como serviço da CI.

A [execução hospedada 40135509840](https://github.com/joaoltrevisan/loja-pedidos-estoque/actions/runs/40135509840) terminou com `success` no commit `2f0fa3d20e2ed7cc225d9d3f0d1e7407571984e2`. Todas as etapas passaram: instalação das dependências, criação da role, estilo, migrations, **251 testes**, OpenAPI e scanner. Os logs registram `Ran 251 tests in 41.442s`; esse é tempo de suíte, não desempenho da API. Os [registros reais](etapa-10-evidencias.txt) preservam os metadados oficiais e os comandos de verificação, com caminhos de usuário anonimizados. A CLI marcou os trechos de log como `UNKNOWN STEP`; os nomes e resultados dos passos estão identificados no JSON oficial.

O [parecer final](etapa-10-parecer.md) registra o alcance da revisão e a sugestão opcional. A revisão não encontrou correções obrigatórias. Fixar também o digest da imagem PostgreSQL ficou como melhoria de reprodutibilidade, sem bloquear esta entrega.

Para executar a mesma suíte localmente no ambiente já preparado:

```bash
python manage.py test tests --noinput --verbosity 2
```

Para executar apenas os três casos novos:

```bash
python manage.py test tests.test_api_concurrency --noinput --verbosity 2
```

Configure antes `DJANGO_SETTINGS_MODULE=config.settings.test` e as variáveis de conexão com um PostgreSQL de desenvolvimento, com role não superusuária e permissão de criar o banco de teste. Para o Docker padrão, use o comando já documentado no README com `docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test app test tests --noinput --verbosity 2`. Após alterações no código, reconstrua a imagem.

## Limites

Não há teste de carga, prova de todos os escalonamentos concorrentes, repetição aleatória de alta duração, servidor HTTP externo, produção ou deploy. As conexões independentes e os bloqueios observados validam os cenários controlados descritos. Não medi percentuais de cobertura nem desempenho nesta etapa. Falhas futuras na CI não devem ser ocultadas por desabilitar testes, remover assertions ou relaxar a autorização.

## Referências

As decisões do workflow seguem a documentação primária do GitHub sobre [serviços PostgreSQL](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers) e [uso seguro das Actions](https://docs.github.com/en/actions/reference/security/secure-use). As versões e opções podem mudar; os SHAs acima registram o código selecionado para esta entrega.
