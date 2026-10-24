# Publicação do código no GitHub

Data: 24/10/2026.

Repositório criado e conferido como **público**: [joaoltrevisan/loja-pedidos-estoque](https://github.com/joaoltrevisan/loja-pedidos-estoque).

Publiquei o projeto na minha conta em repositório público, com cuidados para preservar meus dados pessoais. Conferi a conta de destino antes da criação.

## Conteúdo enviado

O primeiro envio consolidou o trabalho local das Etapas 1 a 7, com implementação, migrations, testes, dados fictícios gerados por comando, decisões, OpenAPI, README e pareceres de revisão. Não se criou um histórico artificial de commits das etapas anteriores.

O [primeiro commit](https://github.com/joaoltrevisan/loja-pedidos-estoque/commit/dc60fbdbc5aa9a021f244a7c0d1f5e90082f475e) foi enviado à branch `main`. O identificador remoto foi comparado ao local e coincidiu; o GitHub confirmou a visibilidade `PUBLIC`. Autor e committer foram conferidos no commit remoto: ambos usam o email `noreply` da conta, sem o email pessoal configurado globalmente no computador.

A Etapa 7 foi aprovada após corrigir a inconsistência de paginação encontrada pelo revisor. As evidências registram **191 testes locais e 191 no Docker**, além de checks, OpenAPI validado e fluxo HTTP isolado. Isso não significa que o GitHub Actions já executou esses testes: a configuração de CI permanece na Etapa 10.

## Privacidade conferida

- A pasta da loja tem repositório Git próprio; outros trabalhos existentes na pasta superior não foram incluídos.
- `.env`, ambientes virtuais, bancos/dados locais e logs privados ficaram fora do versionamento.
- O PDF original e capturas de autenticação não foram publicados.
- Os quatro segredos reais do ambiente local, tokens JWT, padrões de credenciais e email pessoal configurado foram procurados nos arquivos candidatos sem imprimir seus valores.
- Caminhos com usuário do computador foram anonimizados na documentação e nas evidências históricas. As evidências identificam essa redação e preservam resultados.
- A captura publicada do Swagger foi inspecionada: mostra contrato e exemplos fictícios, sem tokens ou dados pessoais.
- Metadados de autor e committer do primeiro commit remoto foram conferidos como `noreply`.

O scanner `scripts/check_publication.py` é uma verificação adicional do conteúdo atual; não oferece garantia absoluta sobre qualquer dado sensível ou alteração futura. O primeiro envio passou com 128 arquivos candidatos, antes de acrescentar este registro de publicação.

## Continuidade

O GitHub hospeda o código, não uma aplicação em produção. A demonstração continua somente na interface local do computador. Não houve deploy público nem integração com pagamentos reais.

Relatórios e seu contrato serão implementados na Etapa 8; avaliação de desempenho e CI permanecem nas etapas seguintes. A Etapa 8 não foi iniciada nesta entrega. Novas etapas continuam sujeitas à revisão técnica antes de avançar.
