# Pacote para revisão técnica — Etapa 4

Situação: implementação e verificações concluídas; **aprovada no escopo definido**, após corrigir o problema obrigatório de login identificado na revisão. Consulte o [parecer final](etapa-04-parecer.md). A integração nos endpoints reais de pedidos permanece pendente para as etapas correspondentes. A Etapa 5 não foi iniciada.

## Critérios da revisão técnica

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

Documento de requisitos: `documento de requisitos fornecido pelo usuario (PDF externo ao repositorio)`, já lido integralmente. Contexto: domínio na Etapa 1 e etapas anteriores aprovadas. O documento descreve requisitos do projeto; o pedido do usuário controla a entrega incremental e exige revisão antes da próxima etapa.

## Arquivos alterados ou adicionados nesta etapa

Todos os caminhos abaixo são relativos à raiz `loja-pedidos-estoque/`. O projeto permanece sem commit no repositório local pai; não houve push, publicação ou deploy.

| Arquivo | Conteúdo |
| --- | --- |
| `requirements.txt` | DRF, SimpleJWT e PyJWT fixados |
| `requirements.lock` | Mesmas dependências na instalação reproduzível |
| `config/settings/base.py` | Autenticação padrão, JSON, JWT e limites de frequência de requisição |
| `config/urls.py` | Inclusão das rotas de autenticação |
| `common/serializers.py` | Rejeição de campos desconhecidos/protegidos e entrada textual estrita |
| `accounts/managers.py` | Busca por email alinhada à expressão Lower da unicidade, incluindo Unicode |
| `accounts/authentication.py` | Validação de ID e autenticação JWT consultando usuário atual |
| `accounts/permissions.py` | Papéis de cliente/admin e leitura de pedidos por dono/admin |
| `accounts/services.py` | Cadastro atômico e atualização de perfil com bloqueio; conflito de email |
| `accounts/serializers.py` | Cadastro, perfil, login e refresh com conta ativa e senha atual |
| `accounts/views.py` | Respostas HTTP, cache privado e permissões públicas explícitas |
| `accounts/urls.py` | Cinco operações em quatro caminhos de autenticação/perfil |
| `orders/selectors.py` | Escopo das consultas de pedidos por usuário |
| `tests/auth_urls.py` | Rotas somente de teste para exercitar autorização sem antecipar a API de pedidos |
| `tests/test_authentication.py` | 27 testes de autenticação/perfil, validação, transações e tokens |
| `tests/test_permissions.py` | 9 testes de papéis, consultas, objetos e alteração de privilégios |
| `tests/test_account_concurrency.py` | 2 testes com conexões PostgreSQL independentes |
| `README.md` | Situação e instruções das rotas disponíveis |
| `docs/etapa-04-autenticacao.md` | Conceitos, contrato, decisões e limites |
| `docs/etapa-04-revisao.md` | Este pacote |
| `docs/etapa-04-evidencias.txt` | Saídas reais de verificações e HTTP, sem segredos/tokens |
| `docs/etapa-04-parecer.md` | Parecer final, problema obrigatório corrigido e sugestão opcional |

Não houve alteração de modelos, migrations ou regras de estoque/pedidos. Os arquivos `.local/` e `.venv/` são recursos locais ignorados; `.env` continua privado e fora do pacote.

## Decisões que merecem avaliação

1. Usuário e cliente são criados juntos. Atualização relê/bloqueia usuário e salva somente campos recebidos; telefone participa da mesma transação. Unicidade no PostgreSQL cobre a corrida entre validação e gravação.
2. A API não aceita privilégios, dono, senha no PATCH ou campos de negócio nesta etapa. Administrador não recebe ações exclusivas de cliente, mesmo se tiver um `Customer` associado.
3. JWT usa a biblioteca mantida; acesso por 5 minutos e refresh reutilizável por 1 dia, sem rotação, extensão de prazo ou logout. Conta atual e alteração de senha são verificadas também no refresh. O tratamento adicional evita erro interno no caso de usuário removido.
4. Limites do cache local do DRF estão explícitos; não há alegação de proteção completa contra força bruta ou prontidão para produção.
5. `orders_visible_to` filtra lista e busca; `CanReadOrder` verifica objeto e recusa escrita. As rotas de teste não existem na URLconf de produção. O critério completo de permissões nos endpoints de pedidos continua pendente para as Etapas 5 a 7, conforme dependência registrada antes da implementação na Etapa 1.

## Verificações realizadas

- 41 testes anteriores + 38 novos = **79 testes** na suíte completa em PostgreSQL local e Docker Linux ARM64.
- Ruff, formatação, `pip check`, checks do Django e ausência de migrations pendentes/novas.
- Dois testes concorrentes usam conexões independentes: mesmo email gera um cliente completo e um conflito; atualização de campos diferentes preserva as duas mudanças.
- HTTP real com clientes/admin fictícios: login, renovação, perfil, ausência de credencial, token inválido, senha incorreta e tentativa de cadastro com privilégio.
- Snapshot completo das nove entidades antes/depois dos testes HTTP, sem exportar dados nem hashes de senha; nenhuma mudança nos dados de demonstração.

Consulte as saídas no [registro de evidências](etapa-04-evidencias.txt). Hash rápido restrito às novas classes de teste; desenvolvimento usa o padrão do Django. Não foram feitas medições de desempenho nem testes das futuras compras, pagamento, cancelamento ou entrega. Não há alegação de compatibilidade com outras arquiteturas.
