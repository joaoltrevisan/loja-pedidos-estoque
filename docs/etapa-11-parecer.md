# Parecer técnico — Etapa 11

Data: 24/10/2026.

**Resultado: aprovada no escopo revisado, sem correções obrigatórias pendentes. A execução hospedada foi conferida.**

## Escopo e conclusão local

A revisão comparou a Etapa 11, página 7 do PDF, com o material de portfólio, o exemplo curl e os registros de verificação, conforme os [critérios](etapa-11-revisao.md). Foi somente de leitura: não alterou código, dados ou ambientes e não repetiu o fluxo HTTP, testes ou medições.

Os nove materiais exigidos e os onze pontos da apresentação estão cobertos. O ER corresponde às relações atuais e distingue unicidade física de existência garantida pelos serviços. As explicações de reserva, rollback, bloqueios, histórico e limites correspondem à implementação.

O roteiro valida a origem local antes de ler configuração, lê `.env` como dados e mantém senhas/tokens em arquivos privados. O curl ignora configuração automática/proxy, não segue redirects e não repete escritas. O administrador é autenticado e tem o papel conferido antes da criação de registros. O exemplo verifica status HTTP, saldos, total, simulação, entrega, cancelamento e recusa por estoque zero.

A documentação reconhece que chamadas confirmadas permanecem após uma falha e que faturamento é global ao período. Não apresenta o roteiro sequencial como prova de concorrência nem tempos SQL como latência da aplicação. Os números de desempenho citados correspondem à evidência da Etapa 9.

## Verificações conferidas

As [evidências](etapa-11-evidencias.txt) registram 24 chamadas HTTP concluídas, saldos **5 → 2 → 2 → 0 → 2**, pedido entregue de `77.70`, cancelamento permitido e rejeição por saldo zero. A auditoria tem zero violações nos sete grupos. Os **251 testes passaram em 20,072 s** no PostgreSQL Docker do ensaio; esse tempo é duração da suíte, não medida de desempenho da API.

A demonstração principal e o `.env` foram preservados. A validação removeu apenas seus recursos exclusivos novos. Os arquivos temporários do roteiro foram removidos após o término.

Na revisão foram executados somente `bash -n`, aprovado, e conferência de **55 links locais**, sem destinos ausentes naquele estado. Pip, Ruff, Django, migrations, OpenAPI, actionlint e as cinco origens negativas foram conferidos nos registros de verificação do desenvolvimento.

## Conferência hospedada

A [execução 40140693590](https://github.com/joaoltrevisan/loja-pedidos-estoque/actions/runs/40140693590) corresponde ao SHA `fe973c017dab8fdd914fe71f04c9e5f0e524b599`, confirmado também no checkout do log. Run, job e todas as etapas oficiais terminaram com `success`.

A conferência final verificou instalação de dependências, bootstrap da role comum, estilo, `bash -n`, migrations, **251 testes em 41,646 s**, OpenAPI e scanner aprovado para **163 arquivos daquele commit**. Esse tempo é duração da suíte, não desempenho da API. A CI confere a sintaxe do roteiro; o fluxo HTTP completo foi validado no ensaio separado, não executado dentro do job hospedado.

No estado documental posterior, o scanner aprovou **171 candidatos** e foram conferidos **57 links locais**, sem destinos ausentes. As evidências registram também 58 atributos do ER conferidos contra os modelos; não houve renderização visual de Mermaid. As contagens de arquivos/links pertencem a momentos distintos e não substituem os registros anteriores.

O commit do usuário `ed0bd57` está preservado no histórico. Sua remoção na seção de tecnologias foi incorporada ao README reorganizado; a documentação da API continua nos guias e no contrato. O exemplo e o workflow não mudaram após o SHA conferido.

A revisão final foi somente de leitura, sem repetir chamadas HTTP, testes ou medições e sem modificar código, dados ou containers. Os materiais e verificações atendem aos critérios da Etapa 11 e encerram as etapas previstas no escopo do projeto. Alterações documentais posteriores também passam pela CI, cujo resultado deve ser conferido no próprio commit.

## Sugestão opcional

Automatizar na CI os cinco casos negativos de origem, além do `bash -n`, reduziria o risco de regressão futura dessa guarda. Arquivos: `examples/demonstracao.sh` e `.github/workflows/ci.yml`. Para verificar, usar configuração inexistente e confirmar rejeição antes da leitura de credenciais ou de qualquer chamada ao curl, inclusive com `PYTHONOPTIMIZE=1`. Os casos manuais registrados e o código atual são suficientes para esta aprovação; não é um bloqueador.

## Limites

A entrega prepara o portfólio e a apresentação do sistema local. Não acrescenta recursos funcionais, cobertura percentual, novas medições de desempenho ou operação de produção. Pagamentos continuam simulados, sem cobrança real. Não há deploy público nem evolução fora do escopo implementada nesta etapa.
