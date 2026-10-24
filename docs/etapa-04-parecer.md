# Parecer técnico da Etapa 4

**Etapa 4 aprovada no escopo definido, sem bloqueadores pendentes.** Houve um problema obrigatório de login, corrigido durante a revisão e coberto por teste de regressão. A integração das permissões nos endpoints reais de pedidos continua exigida nas etapas correspondentes. A Etapa 5 não foi iniciada.

Revisão técnica, seguindo os critérios documentados de revisão e comparando os arquivos com o PDF e as decisões da Etapa 1. O revisor não alterou código, documentação, containers ou dados de demonstração. Os ajustes foram incorporados à implementação e submetidos a nova conferência técnica.

## Problema obrigatório corrigido: equivalência de emails no login

Arquivo: [accounts/managers.py](../accounts/managers.py), método `get_by_natural_key`.

A consulta anterior usava `iexact`, traduzido pelo PostgreSQL para `UPPER`, enquanto a unicidade usa `Lower`. Na localidade `en_US.utf8` do container, emails como `a@ı.example` e `a@i.example` são distintos para `Lower`, mas coincidem para `UPPER`. As duas contas podiam existir; o login encontrava ambas e lançava `MultipleObjectsReturned`, causando erro 500.

O revisor confirmou a diferença com validação em memória e consultas `SELECT`, sem inserir dados. A busca foi corrigida para aplicar `Lower` tanto à coluna quanto ao valor consultado, mantendo a mesma equivalência da restrição de unicidade. O esquema não mudou.

Verificação: `test_login_uses_same_unicode_email_equivalence_as_unique_constraint`, em [tests/test_authentication.py](../tests/test_authentication.py), cadastra as duas contas fictícias com senhas diferentes, confere o ID de cada login e rejeita a senha cruzada. O revisor conferiu sua aprovação nas execuções finais local e Docker, incluindo o metadado `POSTGRES_DATCTYPE=en_US.utf8`.

## Sugestão opcional: demonstrar a espera pelo bloqueio

Arquivo: [tests/test_account_concurrency.py](../tests/test_account_concurrency.py), teste de atualização de campos diferentes.

A barreira sincroniza o início das atualizações, mas não força sobreposição no trecho protegido. O teste verifica a preservação dos campos com conexões independentes, porém pode passar sem demonstrar que uma operação aguardou o bloqueio. Não foi identificado defeito no serviço atual.

Como ampliar a verificação: manter a primeira transação com o bloqueio adquirido, iniciar a segunda, confirmar sua espera e só então liberar a primeira, com sincronização controlada e limites de tempo. Essa melhoria de cobertura permanece opcional e não foi incorporada nesta entrega. A criação de pedidos precisará de seus próprios testes de concorrência na Etapa 5.

## Verificações conferidas e limites

O revisor leu as [evidências finais](etapa-04-evidencias.txt): **79 testes aprovados no PostgreSQL local e 79 na imagem Linux ARM64**, checks do Django, dependências, Ruff, formatação, ausência de migrations novas/pendentes e verificações HTTP. Conferiu o snapshot das nove entidades idêntico antes/depois do HTTP. Não repetiu a suíte completa; os resultados de execução foram registrados nos testes e examinados na revisão.

O parecer considerou adequados cadastro/perfil atômicos, campos protegidos, consulta à conta atual no JWT e distinção entre dono, administrador e conta sem perfil. Nenhum outro problema obrigatório foi encontrado.

As rotas exclusivas de testes validam os componentes de autorização; não encerram a integração de permissões nos futuros endpoints de criação, consulta, cancelamento, pagamento simulado e entrega. Esses pagamentos continuam **simulados, sem cobrança real**. O parecer não afirma prontidão para produção, desempenho ou compatibilidade com outras arquiteturas.
