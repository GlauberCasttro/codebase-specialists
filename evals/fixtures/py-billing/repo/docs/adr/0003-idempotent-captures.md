# ADR 0003 — Captura idempotente por chave

- Status: aceito (2025-06-02)

## Contexto
O gateway reenvia webhooks e o app reenvia a captura em timeout. Em maio houve cobrança dupla
de 14 clientes e lançamento duplicado no ledger.

## Decisão
`PaymentService.capture` exige `idempotency_key`. Chave repetida devolve o mesmo `Payment` sem
chamar o gateway e sem novo lançamento. Reembolsos parciais são permitidos até o valor capturado
(soma dos reembolsos <= capturado).
