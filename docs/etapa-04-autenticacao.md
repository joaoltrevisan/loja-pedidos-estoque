# Etapa 4 — Autenticação e permissões

Esta entrega implementa cadastro de cliente, login, renovação de JWT e leitura/atualização dos próprios dados. As regras de autorização para os próximos endpoints estão preparadas e verificadas com pedidos reais no PostgreSQL, em rotas **exclusivas dos testes**. Compras, cancelamento, pagamento simulado e entregas ainda não têm endpoints. **Todos os pagamentos do projeto permanecem simulados, sem cobrança real.**

## Conceitos e divisão do código

Autenticação responde “quem está fazendo a requisição?”. O login confere email e senha pelo mecanismo do Django e entrega tokens assinados pelo SimpleJWT. O token de acesso acompanha o cabeçalho `Authorization: Bearer <access>`. A assinatura impede adulterar seu conteúdo sem conhecer a chave; o conteúdo do JWT pode ser lido e não deve carregar dados secretos.

Autorização responde “essa pessoa pode executar esta ação sobre este objeto?”. Ter um token válido não transforma um cliente em administrador e não concede acesso ao pedido de outra pessoa. A autenticação consulta o usuário no banco a cada requisição; os privilégios não são copiados para o token. Uma conta desativada ou um administrador que perdeu seu privilégio deixa de passar nas verificações, inclusive usando um token já emitido.

`accounts/serializers.py` valida o formato da entrada e define a resposta; `accounts/services.py` controla transações e validações do cadastro/perfil; os modelos e restrições persistem os dados; `accounts/views.py` apresenta o resultado HTTP. A validação de força da senha também ocorre no serviço, para não depender apenas do endpoint.

## Contrato HTTP disponível

Corpos de entrada são objetos JSON com `Content-Type: application/json`. Campos desconhecidos ou protegidos são rejeitados, em vez de ignorados. Respostas de autenticação/perfil, incluindo erros tratados pelo DRF, usam `Cache-Control: no-store`.

| Método e caminho | Acesso | Entrada e resultado |
| --- | --- | --- |
| `POST /api/auth/register/` | Público | `email`, `name`, `password` e `phone` opcional; cria usuário + cliente; retorna perfil e 201 |
| `POST /api/auth/token/` | Público | `email` e `password`; retorna `access` e `refresh` |
| `POST /api/auth/token/refresh/` | Público, exige refresh válido no corpo | `refresh`; retorna somente um novo `access` |
| `GET /api/auth/me/` | Conta ativa autenticada | Retorna `id`, `email`, `name`, `phone`, `role` do próprio usuário |
| `PATCH /api/auth/me/` | Conta ativa autenticada | Altera apenas `email`, `name` e/ou `phone`; retorna perfil |

Não há rota que aceite ID de outro usuário para atualizar perfil. Um parâmetro de consulta como `?id=123` não muda a identidade obtida da autenticação. `PUT` e `DELETE` do perfil não estão disponíveis.

Exemplo fictício de cadastro:

```json
{
  "email": "novo.cliente@example.com",
  "name": "Cliente Fictício",
  "password": "Exemplo-Ficticio-Portfolio-419!",
  "phone": "11000000000"
}
```

Essa senha é somente um exemplo público. No ambiente de demonstração já preparado, os emails fictícios e a senha local continuam definidos na Etapa 3; a API agora permite fazer login com eles. Nenhuma senha ou token real do ambiente aparece nos registros de verificação.

Regras de entrada: email até 254 caracteres, normalizado para minúsculas sem espaços nas bordas; nome até 150 caracteres, obrigatório e não vazio; telefone opcional com até 20 caracteres e sem validação de operadora, podendo ser apagado com `""`. Telefone não serve como credencial. Senha até 128 caracteres, sem remover seus espaços; os quatro validadores padrão do Django verificam similaridade com o usuário, comprimento mínimo, senhas comuns e senha inteiramente numérica. O Django armazena o hash com sal e algoritmo padrão, nunca a senha em texto.

`role` é somente de leitura: `customer` para cliente; `administrator` para `is_staff=True`; `unassigned` para a situação excepcional de uma conta criada fora do cadastro e sem perfil. Essa última conta pode consultar seus dados, mas não recebe permissões de cliente ou administrador. Administrador não precisa de `Customer`; nesse caso `phone` é `null`. Tentar preencher telefone sem um perfil retorna 400 e não cria um cliente silenciosamente.

Campos como `id`, `user`, `customer`, `password` na atualização, `is_staff`, `is_superuser`, `is_active`, `groups`, `user_permissions`, `role`, `status` e `total` não são graváveis por estas rotas. A criação administrativa continua controlada por comando de gerenciamento; não há endpoint público de promoção. Alteração de senha, recuperação de conta, verificação de email e logout/revogação individual não foram incluídos nesta etapa.

| Situação | Resultado |
| --- | --- |
| Dados inválidos, campo proibido ou email já utilizado | 400, sem alterações parciais |
| Login inválido; token inválido, expirado, adulterado ou de tipo incorreto | 401 |
| Usuário autenticado sem o papel necessário nas rotas de teste | 403 |
| Pedido alheio ou inexistente nas rotas de teste | 404 com a mesma resposta |
| Método não implementado | 405 |
| Corpo com tipo de conteúdo não aceito | 415 |
| Limite de requisições excedido | 429 com `Retry-After` |

## Decisões sobre tokens e segurança

O acesso vale **5 minutos** e o refresh **1 dia** desde sua emissão. A renovação não estende a validade original do refresh. O refresh é reutilizável nesse prazo; não há rotação, blacklist nem promessa de bloquear a reutilização de um refresh roubado nesta entrega. A chave de assinatura HS256 vem da configuração secreta do Django, gerada localmente e excluída da imagem/repositório. A validação também exige audiência `loja-api` e emissor `loja-portfolio-local`.

Contas desativadas, removidas e tokens emitidos antes de uma alteração de senha são rejeitados tanto no acesso quanto na renovação. `CHECK_REVOKE_TOKEN` usa o mecanismo da biblioteca para comparar uma impressão do hash de senha atual; o token não contém a senha nem o hash armazenado no banco. A validação do ID exige uma string de inteiro positivo dentro do intervalo da chave no PostgreSQL, evitando coerções inesperadas ou erros internos com claims inválidos.

Foi necessário tratar explicitamente a renovação: no [código publicado do SimpleJWT 5.5.1](https://github.com/jazzband/djangorestframework-simplejwt/blob/v5.5.1/rest_framework_simplejwt/serializers.py), a busca do usuário não trata `DoesNotExist`, e o refresh não confere a alteração de senha. `ActiveUserRefreshSerializer` mantém a verificação de assinatura, prazo e tipo na biblioteca e acrescenta essas verificações. Os testes cobrem os casos. Essa é uma adaptação de integração, não uma implementação própria de criptografia.

O DRF exige autenticação por padrão; as entradas públicas são declaradas explicitamente. Cadastro/login/refresh ignoram um cabeçalho de acesso vencido, pois usam suas próprias credenciais. Não há autenticação por sessão ou cookies nesta API. A sonda `/health/` permanece pública e sem dados de domínio.

Como não existe proxy neste ambiente, o limite usa o endereço da conexão e ignora `X-Forwarded-For` informado pelo cliente; há teste para essa tentativa de contorno. Há limites básicos por IP nas entradas públicas: cadastro 5/minuto, login 20/minuto e refresh 60/minuto; perfil 120/minuto por usuário autenticado. O cache local do DRF é uma proteção básica de desenvolvimento, sujeita a reinícios, múltiplos processos e condições de corrida; não é defesa completa contra força bruta. Nenhuma validação de produção ou exposição pública foi realizada. O ambiente atende apenas em `127.0.0.1`, como na Etapa 3.

## Integridade e concorrência

Cadastro cria `User` e `Customer` dentro da mesma transação. Uma falha ao gravar o perfil desfaz a criação do usuário. A busca de login utiliza a mesma expressão `Lower` da restrição de unicidade, tanto na coluna quanto no valor consultado. A revisão identificou que `iexact` usa `UPPER` no PostgreSQL e pode confundir dois emails Unicode aceitos e distintos para `Lower`, causando erro 500. O manager foi corrigido e o teste de regressão cadastra contas fictícias em `ı.example` e `i.example`, verifica os dois logins e rejeita a senha cruzada. Não há alteração do esquema.

A unicidade de email no PostgreSQL protege inclusive duas requisições que passam pela validação antes de gravar. Somente as violações das restrições de email conhecidas são convertidas em conflito de validação; falhas de integridade diferentes não são escondidas.

A atualização bloqueia e relê a linha do próprio usuário com `select_for_update()`, grava apenas os campos permitidos recebidos e inclui o telefone na mesma transação. Assim, duas atualizações de campos diferentes preservam ambas as mudanças e não sobrescrevem senha/privilégios lidos anteriormente. Se duas atualizações mudarem o mesmo campo, a última a adquirir o bloqueio prevalece. Isso não constitui controle de versões otimista. Cadastro concorrente e atualização de campos diferentes foram testados com conexões PostgreSQL independentes.

## Autorização preparada para os pedidos

| Componente | Responsabilidade |
| --- | --- |
| `IsCustomer` | Exige conta ativa, perfil de cliente e ausência de papel administrativo |
| `IsStoreAdmin` | Exige conta ativa com `is_staff=True` |
| `CanReadOrder` | Permite somente leitura pelo dono ou administrador; nunca concede escrita |
| `orders_visible_to(user)` | Filtra a consulta antes de listar ou buscar por ID; cliente vê apenas seus pedidos |

Filtrar a lista é necessário: a permissão de objeto do DRF não é chamada para cada item de uma listagem. O filtro também faz um ID alheio se comportar como inexistente. A permissão de objeto fornece uma segunda verificação. As operações futuras de criação/cancelamento/pagamento/envio exigirão suas próprias autorizações e validações de estado.

Conforme a dependência já registrada na Etapa 1 e o PDF, **o critério completo de permissões nos endpoints reais de pedidos continua pendente**. `tests/auth_urls.py` liga os componentes em pequenas rotas de teste, usa JWT real e pedidos no banco, mas não é incluído em `config/urls.py`. Esses testes não alegam verificar criação, cancelamento, pagamento ou envio HTTP. O uso efetivo dos componentes e os testes de adulteração de dono, preço, total e estado nos pedidos serão exigidos quando cada endpoint for entregue nas Etapas 5 a 7.

## Versões e verificação

Foram fixados DRF **3.18.3**, SimpleJWT **5.5.1** e PyJWT **2.15.1**, mantendo Django 5.2.18 e Python 3.12.15. Fontes consultadas em 23/10/2026: [requisitos do DRF](https://www.django-rest-framework.org/#requirements), [metadados oficiais do SimpleJWT](https://pypi.org/project/djangorestframework-simplejwt/), [configurações do SimpleJWT](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/settings.html) e [PyJWT](https://pypi.org/project/PyJWT/). Os metadados do SimpleJWT incluem Django 5.2; a lista de versões na página estável de introdução está desatualizada em relação a esses metadados. Não presumimos uma matriz completa de compatibilidade: a combinação fixada foi verificada pela suíte deste projeto no PostgreSQL e em Linux ARM64.

Os testes cobrem autenticação, escopo de dados, privilégios, transações, tokens e duas situações concorrentes de contas. Nos testes novos, o hasher rápido MD5 fica limitado às classes de teste para reduzir custo; as configurações de desenvolvimento mantêm o algoritmo padrão do Django. Isso não substitui testes de concorrência das compras ou medições de desempenho, previstos nas etapas seguintes.

Os comandos reproduzíveis continuam no README; resultados reais e arquivos desta etapa estão no [pacote de revisão](etapa-04-revisao.md) e no [registro de evidências](etapa-04-evidencias.txt).
