# Pacote para revisão técnica — Etapa 7

Situação: aprovada em revisão técnica independente, após corrigir uma inconsistência de paginação. Consulte o [parecer final](etapa-07-parecer.md). A Etapa 8 não foi iniciada.

## Critérios da revisão técnica

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

Documento de requisitos: PDF externo fornecido pelo usuário, lido integralmente e relido nesta entrega. O arquivo original não integra o repositório público. O desenvolvimento segue entregas separadas e revisão antes da próxima etapa.

## Escopo e dependências

A [explicação da etapa](etapa-07-api.md) registra contrato, regras, exemplos, limites e decisões. O PDF inclui relatórios na Etapa 7 antes de definir suas consultas na Etapa 8; essa inconsistência foi explicada antes da implementação. A API operacional é entregue agora; os endpoints e o OpenAPI de relatórios permanecem explicitamente pendentes para a Etapa 8, sem placeholders de cálculo.

## Arquivos alterados ou adicionados nesta etapa

| Arquivos | Entrega |
| --- | --- |
| `catalog/services.py` | Validação pura do produto, criação com estoque zero, atualização com bloqueio e conflito de SKU |
| `catalog/serializers.py`, `catalog/views.py`, `catalog/urls.py` | Catálogo autenticado, ativos para cliente, escrita administrativa, filtros e paginação |
| `inventory/services.py` | Entradas/ajustes com autorização atual, limites, bloqueios e saldo/movimento atômicos |
| `inventory/serializers.py`, `inventory/views.py`, `inventory/urls.py` | Saldos, auditoria e escrita controlada de movimentos |
| `orders/views.py`, `orders/serializers.py`, `orders/urls.py` | Lista/detalhe com escopo antes da busca, histórico/pagamento/envio e validação documentável dos itens/endereço |
| `common/validation.py` | Papel atual do administrador, IDs no intervalo e texto válido |
| `common/api.py`, `common/queries.py` | Envelope de erros, parâmetros estritos, ordenação permitida e paginação |
| `common/serializers.py`, `common/views.py` | Tipos JSON estritos, limites monetários/texto Unicode, errors nulo nos conflitos existentes |
| `common/schema.py` | Anotações OpenAPI, JWT, exemplos fictícios e regras/perfis por operação |
| `config/settings/base.py`, `config/urls.py`, `config/views.py` | OpenAPI/Swagger com assets locais e rotas novas |
| `requirements.txt`, `requirements.lock` | Versões fixadas de OpenAPI/Swagger e transitivas |
| `tests/test_api_catalog_stock.py` | 17 testes de catálogo, estoque, permissões, validação e rollback |
| `tests/test_api_read_docs.py` | 13 testes de consulta, autorização real, N+1, documentação e erros |
| `tests/test_catalog_stock_concurrency.py` | 9 testes com espera real observada no PostgreSQL |
| `tests/test_authentication.py`, `tests/test_order_creation.py` | Atualização do envelope de erro e de métodos agora disponíveis; preservadas verificações anteriores |
| `scripts/check_publication.py` | Varredura local de arquivos candidatos para publicação, sem imprimir valores privados |
| `README.md`, `docs/etapa-07-api.md`, `docs/etapa-07-revisao.md` | Execução, conceitos, decisões e revisão |
| `docs/etapa-07-parecer.md` | Parecer, problema de paginação corrigido e limites da aprovação |
| `docs/openapi.yaml`, `docs/etapa-07-swagger.png` | Contrato exportado/validado e captura conferida do Swagger sem autenticação |
| `docs/etapa-07-evidencias.txt` | Saídas reais locais, Docker e HTTP; caminhos pessoais anonimizados |
| Documentação/evidências anteriores | Apenas anonimização dos caminhos pessoais para a publicação autorizada; resultados preservados e redação identificada nas evidências |

Nenhum modelo, migration ou regra de transição da Etapa 6 foi alterado. Não foram criados relatórios, índices, CI ou uma interface de compras nesta etapa.

## Decisões para conferir

- Produto novo tem saldo zero criado na mesma transação; estoque não é editável pelo catálogo.
- Preço usa texto decimal na API; saldo/deltas exigem inteiros JSON; perfil, responsáveis, datas e valores históricos são definidos no servidor.
- Administrador atualiza/inativa produto; cliente só consulta ativos. Não existe exclusão física pela API.
- Entradas e ajustes bloqueiam produto antes de estoque; alteração de preço/atividade bloqueia o produto para coordenar com compras. Não há ordem inversa de aquisição.
- Saldo e movimento confirmam ou voltam juntos; limite de saldo verificado antes da escrita. Ajustes não reescrevem reservas.
- Lista e detalhe de pedidos filtram a visibilidade antes de retornar dados; pedido alheio e inexistente têm a mesma resposta.
- Ordenação usa mapeamento explícito e desempate por ID; parâmetros desconhecidos, repetidos, vazios ou fora de limite falham.
- Erros de validação agora ficam em `errors`, ao lado de `code` e `detail`; a alteração de contrato foi documentada.
- `select_related` para pagamento/envio e `prefetch_related` ordenado para itens evitam consultas por pedido; não há afirmação de ganho de desempenho medido.
- Swagger/contrato são públicos e só contêm exemplos fictícios. Assets são locais e a autorização não persiste; não há validador externo.
- O pacote aceita a combinação instalada pelos metadados, mas o mantenedor lista DRF até 3.17; a compatibilidade com 3.18.3 foi verificada neste projeto sem atribuir suporte oficial adicional.

## Resultados registrados

As [evidências](etapa-07-evidencias.txt) registram:

- **191 testes locais e 191 no Docker Linux ARM64**, aprovados (152 anteriores + 39 novos).
- Checks Django, migrations sem alteração, dependências, Ruff e formatação aprovados.
- OpenAPI validado com `--validate --fail-on-warn`, sem warnings ou erros.
- Nove disputas novas com conexões independentes e espera real observada, incluindo dois ajustes, ajustes contra compra/cancelamento, preço/atividade contra compra e SKU duplicado.
- Fluxo HTTP isolado com catálogo, saldo, compra histórica, pagamento simulado, envio, entrega, cancelamento e ajuste, com soma dos movimentos igual ao saldo.
- Demonstração principal idêntica antes/depois; recursos do ensaio removidos.
- Swagger renderizado no navegador com assets locais e sem dados privados na captura.

Os tempos de execução impressos são duração de suíte; não são medições de desempenho da aplicação. A revisão deve avaliar código e evidências sem alterar o projeto.

## GitHub e privacidade

Publiquei meu desenvolvimento em `joaoltrevisan/loja-pedidos-estoque`, como repositório público, com verificações para evitar exposição de dados pessoais. A pasta do projeto agora tem repositório próprio, separado dos outros trabalhos. `.env`, bancos, logs privados e ambientes virtuais ficam ignorados. Caminhos pessoais foram anonimizados na documentação histórica. O scanner verifica segredos locais, tokens, email pessoal configurado, caminhos e arquivos locais antes do envio; não constitui garantia absoluta de ausência de dados sensíveis.

O primeiro commit usa nome público da conta e email `noreply`; não há commits anteriores com email pessoal neste repositório recém-criado. A autenticação da CLI foi concluída e a conta de destino foi conferida. A criação/envio remoto foi conferida após a revisão; veja o [registro de publicação](publicacao-github.md). Não houve deploy público da aplicação.
