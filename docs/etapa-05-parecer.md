# Parecer técnico da Etapa 5

**Etapa 5 aprovada, sem problemas obrigatórios identificados e sem bloqueadores para encerrar a entrega.** A Etapa 6 não foi iniciada.

Revisão técnica, seguindo os critérios documentados de revisão. Foram comparados os arquivos atuais com o PDF, incluindo serviço, validação, serializers, endpoint, gerador, testes e evidências finais. O revisor não alterou código, documentação, containers ou dados e não repetiu a suíte.

## Avaliação

- O servidor determina dono, preço, total, estado e dados históricos; campos protegidos são rejeitados.
- Produtos e estoques são bloqueados em ordem consistente. Atividade e disponibilidade são verificadas dentro da transação.
- Pedido, itens, redução de saldo e reservas persistem juntos. O teste de falha provoca uma exceção depois das gravações e comprova rollback integral.
- Os sete testes concorrentes usam conexões independentes, identificam PIDs distintos e observam espera real no PostgreSQL antes de liberar o primeiro ator.
- O gerador reutiliza o serviço de criação e preserva a coerência dos dados fictícios. Os pagamentos continuam explicitamente **simulados, sem cobrança real**.

O revisor conferiu as [evidências finais](etapa-05-evidencias.txt): **109 testes aprovados no PostgreSQL local e 109 no Docker Linux ARM64**, checks aprovados e compra HTTP em banco temporário com total `77.70`, saldo `26 → 23`, reserva `-3` e nenhum pagamento ou entrega novo. O dataset principal foi preservado e os recursos temporários removidos.

O deadlock da rodada inicial foi registrado corretamente. A correção do cenário artificial manteve a verificação do bloqueio de estoque e não enfraqueceu a garantia exigida para as compras. A ocorrência inicial não foi contada como execução aprovada.

## Problemas e sugestões

Nenhum problema obrigatório foi identificado na versão final. O revisor não identificou sugestões opcionais novas que justificassem ampliar esta entrega.

## Limites do parecer

Listagem/detalhe, API completa e transições continuam pendentes nas etapas previstas; esta aprovação não as considera verificadas. Não há conclusão sobre desempenho, outras arquiteturas, prontidão para produção ou concorrência das operações da Etapa 6. Não houve publicação, deploy ou envio ao GitHub.
