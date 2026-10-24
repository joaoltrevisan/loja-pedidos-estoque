# Revisão técnica — Etapa 11

Situação: aprovada, sem correções obrigatórias pendentes; consulte o [parecer final](etapa-11-parecer.md). As onze etapas do escopo foram concluídas.

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

Escopo: Etapa 11, página 7 do PDF, preservando as regras das etapas anteriores. O PDF original não integra o repositório público. A especificação exige material de portfólio e onze pontos de demonstração; não pede novos recursos de domínio ou deploy.

## Correspondência das entregas

| Requisito | Material atual |
| --- | --- |
| README em português | `README.md`, preservando o título e a introdução definidos no repositório |
| Diagrama ER | `docs/arquitetura.md`; campos completos definidos na Etapa 2 e modelos/migrations atuais |
| Documentação da API | `docs/api.md`, `docs/openapi.yaml`, Swagger local e guias de contratos das etapas anteriores |
| Guia de execução | `docs/execucao.md`, com primeira execução, retomada, atualização e projeto isolado |
| Exemplos curl | `examples/demonstracao.sh`, executável via Bash e validado com chamadas reais |
| Relatório de desempenho | `docs/etapa-09-desempenho.md` e os planos JSON, sem atribuir medições novas ao roteiro |
| Transações e concorrência | `docs/arquitetura.md`, decisões detalhadas das etapas anteriores e matriz dos testes |
| Dados fictícios | `seed_demo` existente e os registros exclusivos criados pelo roteiro |
| Limitações e próximos passos | `docs/limites-e-proximos-passos.md` |
| Onze pontos da apresentação | `docs/demonstracao.md`, com sequência, endpoints, resultados e explicações |

## Arquivos alterados

| Arquivo | Responsabilidade |
| --- | --- |
| `README.md` | Entrada de portfólio mais direta, navegação, execução, testes, desempenho e histórico |
| `docs/execucao.md` | Guia atual de execução/recuperação, persistência e ambientes separados |
| `docs/arquitetura.md` | ER atual, estados, camadas e garantias transacionais |
| `docs/api.md` | Entrada do contrato, recursos, papéis, erros e listas |
| `docs/demonstracao.md` | Onze pontos, comandos, resultados reais e limites do roteiro |
| `docs/limites-e-proximos-passos.md` | Escopo e limites atuais, evoluções não implementadas |
| `examples/demonstracao.sh` | Fluxo curl local com credenciais em arquivos privados, checagem de status e resultados |
| `.github/workflows/ci.yml` | Acrescenta `bash -n` ao passo de estilo para conferir a sintaxe do exemplo |
| `docs/etapa-11-evidencias.txt` | Ensaio real desde base vazia, fluxo, auditoria, 251 testes e preservação da base anterior |
| Este arquivo e `docs/etapa-11-parecer.md` | Critérios, achados e fechamento da revisão |

Não há alteração de modelos, migrations, serviços, contratos HTTP ou dependências da aplicação. Documentos antigos permanecem como registros históricos; os novos guias apresentam o estado atual.

## Decisões para conferir

- O exemplo recusa origens externas, URLs com credenciais/caminhos/parâmetros e protocolos diferentes de HTTP local antes de ler configuração ou fazer requisição.
- O curl ignora configuração automática, desabilita proxy, não segue redirects, tem timeout e não repete POST automaticamente.
- `.env` é lido como dados; não é executado. Apenas a senha fictícia do administrador é usada. Cadastro gera senha nova e email `@example.com`.
- Autorização e JSON são passados ao curl por arquivos em diretório privado/umask 077. Não há senha/token na linha de comando ou nos logs do roteiro. O diretório é removido em término/falha normais; interrupção forçada é uma limitação documentada.
- O script autentica e confere o administrador antes de criar registros. Cada execução cria registros próprios, sem resetar a base; uma falha não desfaz chamadas HTTP já confirmadas.
- O exemplo mostra reserva na criação, saldo preservado no pagamento/envio/entrega e devolução somente no cancelamento permitido.
- A compra sem estoque realmente usa um produto com saldo zero, retorna 409 e não cria um oitavo pedido no ensaio.
- A soma de faturamento é global ao período. O valor de 77.70 descreve o ensaio isolado; o script não afirma igualdade global em toda base reutilizada.
- Concorrência e desempenho não são inferidos do roteiro sequencial: remetem aos testes e às medições reais das etapas anteriores.
- A execução de limpeza da validação removeu somente o projeto/volume/rede/imagem de nome novo criado pelo ensaio. Os guias de uso param preservando volumes por padrão.
- Pagamentos são identificados como simulados e as limitações de produção não são apresentadas como recursos já implementados.

## Verificações registradas

No ambiente novo: `config --quiet`, build, banco saudável, migrations, `seed_demo`, aplicação saudável e 24 chamadas curl concluídas. Saldos 5 → 2 → 2 → 0 → 2, pedido entregue 77.70, segundo cancelado, terceiro rejeitado por saldo zero. Faturamento/ticket atuais 77.70 no ensaio. A auditoria retornou zero violações em sete grupos.

A base começou com 5 pedidos e terminou com 7, com 5 usuários, 4 clientes, 5 produtos, 5 estoques, 9 itens, 4 pagamentos simulados, 3 remessas e 15 movimentos. Os 251 testes passaram em PostgreSQL no Docker; os registros do roteiro permaneceram iguais depois da suíte. Pip, Ruff/formatação, Django, migrations e OpenAPI também passaram. Bash e actionlint passaram. Cinco URLs inválidas foram recusadas antes da leitura de credenciais, inclusive com `PYTHONOPTIMIZE=1`.

A demonstração principal conservou o hash dos nove modelos `013f437a83e0cea887b3cff4ab81939c2fb4b8d5767d6f3068f6067a43df0483`, seus 5 pedidos e saldos 26/17/45. O `.env` permaneceu igual, e a pasta temporária do roteiro ficou vazia após o término. Os recursos do ensaio novo foram removidos.

A revisão deve distinguir conferência das evidências de repetir testes/medições. A execução hospedada 40140693590 foi aprovada no SHA `fe973c017dab8fdd914fe71f04c9e5f0e524b599`, com 251 testes e todas as etapas aprovadas. O parecer registra a conferência dos logs e metadados, distinta do ensaio Docker. O commit documental final também tem sua CI acompanhada. Não publicar aplicação, imagem ou dados locais.
