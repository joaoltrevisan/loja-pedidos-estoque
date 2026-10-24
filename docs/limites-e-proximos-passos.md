# Limites e próximos passos

Este projeto de portfólio usa dados fictícios e pagamentos **simulados, sem cobrança real**. Os indicadores financeiros não são apuração contábil ou fiscal. O código é público; a aplicação funciona localmente.

## Escopo funcional atual

Há cadastro e JWT, dois papéis, catálogo, disponibilidade e auditoria de estoque, criação transacional, pagamento simulado, cancelamento de pendente, envio/entrega e sete relatórios. O estoque é reservado na criação do pedido. Produtos inativos não recebem novas compras, mas o histórico permanece.

Não há frete calculado, descontos, impostos, múltiplos depósitos, carrinho, fornecedor, estorno, devolução, parcelamento ou integração externa. Código de rastreio é apenas texto fictício. Não há interface de loja para consumidor; a apresentação usa API/Swagger/curl.

## Integridade e concorrência

As operações da API são transacionais e o banco aplica restrições locais. As invariantes entre tabelas dependem de usar os serviços; não há proteção contra toda escrita administrativa arbitrária por SQL. Uma inconsistência detectada no histórico rejeita a ação, sem reparo silencioso.

A criação não tem chave de idempotência: repetir um POST cria outro pedido se houver saldo. Reservas pendentes não expiram automaticamente. Uma chamada HTTP que perde a resposta pode ter confirmado; clientes não devem repetir escritas indiscriminadamente. Repetições permitidas das ações de transição têm regras específicas.

A suíte controla cenários concorrentes e observa bloqueios reais no PostgreSQL. Não é prova de todos os escalonamentos possíveis, ausência universal de deadlock ou teste de carga. Falhas de conexão, recuperação de desastre, backup e restauração de produção não foram validados.

## Segurança e operação

O Compose é de desenvolvimento: servidor Django, bind da aplicação em loopback e banco sem porta publicada. Não foi preparado deploy público, TLS, proxy de produção, observabilidade/alertas, política de backups ou gestão de segredos de produção. `CREATEDB` existe para os bancos de teste e experimentos e não define uma role recomendada para produção.

JWT usa biblioteca mantida, prazos e verificações de usuário/senha/papel, mas não há logout com revogação individual de token ou rotação de refresh. Os limites por escopo usam cache local, sem garantia distribuída ou substituição de controles operacionais. A chave pública de `config.settings.test` é exclusiva dos testes.

A CI usa credenciais públicas descartáveis apenas para seu PostgreSQL temporário; não recebe o `.env` local. Actions são fixadas por SHA e bibliotecas por versão. O lock não inclui hashes de todas as distribuições e as imagens são fixadas por tag de versão, sem digest; atualizações devem ser deliberadas. A CI verifica testes/estilo/contrato/migrations, mas não realiza auditoria automatizada de vulnerabilidades nem impõe proteção de branch.

A CI confere a sintaxe do roteiro curl. Os cinco casos negativos de origem foram executados manualmente; automatizá-los na CI ficou como melhoria opcional da revisão final. O fluxo HTTP completo também foi ensaiado em ambiente separado, não dentro do job hospedado.

O scanner de publicação procura valores privados locais conhecidos, padrões de credencial e caminhos pessoais no conteúdo atual. Não prova ausência de todo dado sensível nem substitui revisão de histórico, imagens e alterações externas. Os commits usam email `noreply`; credenciais locais ficam ignoradas pelo Git.

## Leituras e desempenho

Cada resposta de faturamento usa um agregado coerente. Não existe um snapshot global entre chamadas ou páginas. Os relatórios limitam o período a 366 dias e usam São Paulo com início inclusivo/fim exclusivo.

O [experimento da Etapa 9](etapa-09-desempenho.md) mediu sete consultas, 20 mil pedidos e cache aquecido. Houve ganho em acessos seletivos e nenhum ganho demonstrável no faturamento anual. Os custos de espaço e construção foram medidos; custo de escrita, cache frio, p95/p99 da API, throughput e carga concorrente não foram medidos. Não é previsão de desempenho de produção.

Uma interrupção ao gravar a evidência do benchmark pode deixar JSON parcial. A criação exclusiva evita sobrescrever evidência anterior, mas publicar um temporário completo continua como melhoria opcional. Use somente saídas concluídas e JSON válido.

## Prioridades para uma evolução futura

1. Definir o comportamento de repetição de criação e acrescentar chave de idempotência com unicidade/transação, incluindo testes de disputa e timeout.
2. Definir prazo e política de expiração de reservas antes de criar um processamento assíncrono; testar disputa entre expiração, pagamento e cancelamento.
3. Se houver intenção de exposição pública, projetar operação e segurança de produção, incluindo servidor, TLS, segredos, role mínima, cache, logs e backups, com autorização separada para deploy.
4. Ampliar cenários de carga e distribuição, medir latência da API e custo de escrita e rever índices com novas evidências.
5. Melhorar reprodutibilidade das dependências/imagens, política de atualização, auditoria de vulnerabilidades e publicação atômica dos resultados do benchmark.

Esses itens são propostas fora da entrega atual. Não foram implementados ou apresentados como garantias existentes.
