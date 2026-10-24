# Etapa 3 — Entrega para revisão técnica

## Critérios da revisão técnica

> Revise a etapa implementada comparando os arquivos atuais com os requisitos do PDF. Procure erros de lógica, integridade dos dados, segurança, concorrência e testes ausentes. Diferencie problemas que precisam ser corrigidos de sugestões opcionais. Para cada problema, indique o arquivo, explique o impacto e descreva como verificar a correção. Não altere o código nesta revisão.

PDF de referência: `documento de requisitos fornecido pelo usuario (PDF externo ao repositorio)`. O escopo atual é a Etapa 3, página 3. A Etapa 2 foi revisada antes desta implementação e recebeu [parecer favorável](etapa-02-parecer.md).

## Situação e evidências

**Etapa concluída e aprovada na revisão complementar.** A Etapa 4 não foi iniciada. Ver [decisões e ambiente](etapa-03-ambiente.md), [saída local anterior](etapa-03-evidencias.txt), [execução Docker](etapa-03-docker-evidencias.txt) e [parecer final](etapa-03-parecer.md).

Além das verificações locais anteriores, foram aprovados 41 testes dentro do container com PostgreSQL 17.11. Foram conferidos build Linux, inicialização pelo entrypoint oficial, mounts, permissões, rede, saúde HTTP, role, dados fictícios e persistência após recriar os containers. A evidência registra também a recusa esperada do seed repetido e uma coleta de metadados ajustada após ausência da tag base no image store.

## Arquivos criados nesta entrega

- `Dockerfile`, `.dockerignore`, `.env.example`, `compose.yaml`.
- `docker/postgres/01-app-role.sql`.
- `config/views.py`.
- `orders/demo_data.py`.
- `orders/management/__init__.py`, `orders/management/commands/__init__.py`, `orders/management/commands/seed_demo.py`.
- `scripts/__init__.py`, `scripts/create_env.py`.
- `tests/test_demo_data.py`, `tests/test_environment.py`, `tests/test_health.py`.
- `docs/etapa-02-parecer.md` (registro da revisão anterior).
- `docs/etapa-03-ambiente.md`, `docs/etapa-03-evidencias.txt`, `docs/etapa-03-revisao.md`.
- `docs/etapa-03-parecer.md` (parecer independente condicionado à validação Docker).
- `docs/etapa-03-docker-evidencias.txt` (execução real e fechamento da pendência Docker).

## Arquivos atualizados

- `README.md`: roteiro completo e situação real da entrega.
- `config/settings/base.py`: hosts por ambiente e habilitação do gerador.
- `config/urls.py`: somente a sonda operacional de saúde.
- `docs/etapa-02-revisao.md`: link para o parecer aprovado.
- `docs/etapa-02-modelagem.md`: situação atualizada após o parecer, sem mudança de regras.

Nenhum modelo ou migration da Etapa 2 foi alterado. `.env` foi gerado localmente com permissão 0600, não é exibido e está ignorado tanto no Git quanto no contexto da imagem. Instalações e logs em `.local` e `.venv` também permanecem ignorados.

## Foco da revisão

Conferir segredos e inicialização do banco; role sem superusuário; usuário sem root e filesystem somente leitura; prontidão do servidor definitivo; coerência do gerador com itens, estoque, movimentos, pagamentos simulados e entregas; rollback e comportamento em base preenchida. Verificar se o roteiro realmente funciona em ambiente limpo quando houver Engine disponível.

Os serviços de compra e transição ainda pertencem às etapas 5 e 6. O construtor de dataset não deve ser apresentado como implementação desses serviços, nem os testes do gerador como prova de concorrência das compras.

Revisão inicial e complemento registrados no [parecer independente](etapa-03-parecer.md). A pendência de Compose foi resolvida, e o revisor não identificou bloqueadores restantes para encerrar a etapa. Ele conferiu a evidência, verificou os dois serviços saudáveis e repetiu a requisição HTTP; não repetiu a suíte nem alterou código. O código da aplicação, Dockerfile, Compose, modelos e migrations não precisou de alteração para passar pela execução real.
