# Parecer técnico da Etapa 3

**Situação atual: aprovada após a revisão complementar da execução real em Docker. Nenhum bloqueador restante identificado para encerrar a Etapa 3.**

## Revisão inicial

Revisão técnica em 23/10/2026, seguindo os critérios documentados de revisão. Foram comparados os arquivos atuais com a Etapa 3 do PDF. Nenhum código ou documento foi alterado pelo revisor.

Resultado inicial: nenhum problema obrigatório concreto adicional identificado nos arquivos; aprovação final condicionada à execução real com Docker. Naquele momento a Etapa 3 ainda não estava concluída.

## Pendência da revisão inicial (resolvida)

O roteiro do README precisava ser executado em um projeto/volume Docker novo. Faltava comprovar em conjunto build Linux, dependências, entrypoint oficial, mounts, permissões e comunicação entre containers. `compose config` e execução local não substituíam essa evidência.

Verificação necessária: construir imagem; iniciar banco e conferir a role; aplicar migrations; gerar dados fictícios; iniciar aplicação; verificar saúde; executar testes dentro do container; reiniciar preservando os dados; registrar os resultados reais. Enquanto essa pendência permanecer, não iniciar a Etapa 4.

## Avaliação dos arquivos

O revisor considerou coerentes o usuário sem root, filesystem somente leitura, `/tmp` gravável, exclusão do `.env` da imagem, separação de credenciais, escape do bootstrap SQL, sonda sem detalhes internos e construtor de dataset transacional em base vazia. Conferiu que o gerador preserva itens, totais, pagamentos simulados, entregas, saldos e movimentos, sem alegar implementar os serviços futuros de compra.

Na revisão inicial, o revisor conferiu o registro dos 41 testes locais aprovados. Não repetiu a suíte nem declarou, naquele momento, resultado de execução em container ou desempenho.

## Sugestões opcionais

1. Em `tests/test_demo_data.py`, ampliar o snapshot de reprodutibilidade para incluir itens históricos, endereço, entrega e movimentos. Impacto: ampliar proteção contra regressões; verificar igualdade dos valores de negócio em duas bases vazias, desconsiderando IDs e hashes.
2. Em `orders/demo_data.py`, testar futuramente duas execuções simultâneas do gerador com conexões independentes. Verificação: uma conclui e a outra espera para então recusar a base preenchida, sem duplicação. Esse teste comprovaria apenas o contrato do gerador, não concorrência de compras.

As sugestões não foram incorporadas nesta entrega e permanecem opcionais, sem impedir o fechamento.

## Revisão complementar após a execução Docker

O revisor conferiu o [registro completo de Docker](etapa-03-docker-evidencias.txt) e a documentação atualizada em 23/10/2026. Aprovou a resolução da pendência: projeto e volume novos, build Linux ARM64, bootstrap oficial, migrations, dataset fictício, **41 testes aprovados dentro do container**, Ruff, formatação, UID e permissões, role, saúde HTTP e persistência após recriar os containers.

Conferiu a recusa esperada do seed repetido, com dados preservados, e a distinção entre a coleta inicial de metadados que falhou e a validação funcional que passou. O digest da base está no build, e as imagens efetivamente registradas foram inspecionadas em seguida.

O revisor fez duas verificações adicionais de leitura:

- `docker --context desktop-linux compose -p loja-stage3-20261023223148 ps`: aplicação e banco em execução e saudáveis.
- `curl --fail --silent --show-error --max-time 5 http://127.0.0.1:18003/health/`: `{"status":"ok"}`, código zero.

Não alterou código ou documentação, não repetiu a suíte e não removeu ou encerrou containers ou volumes. Não identificou novos problemas obrigatórios. A Etapa 3 está aprovada; a Etapa 4 não foi iniciada nesta entrega.

Limites: validação realizada em Linux ARM64 neste ambiente de desenvolvimento. Não comprova outras arquiteturas, concorrência das futuras compras ou desempenho. Esses limites não impedem concluir o escopo da Etapa 3.
