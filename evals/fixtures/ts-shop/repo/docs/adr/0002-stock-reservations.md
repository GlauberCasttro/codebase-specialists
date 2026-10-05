# ADR 0002 — Reserva de estoque com TTL de 15 minutos; estoque nunca negativo

- Status: aceito (2025-05-30)

## Contexto
Na Black Friday de teste, duas reservas concorrentes deixaram `available` em -3 e vendemos o que
não tínhamos.

## Decisão
- `available` de um SKU **nunca** fica negativo: `reserve` falha com `InsufficientStockError`
  antes de alterar o saldo (packages/api/src/inventory/stock.ts).
- Uma reserva expira em **15 minutos** (`RESERVATION_TTL_MS`) e devolve o estoque ao expirar;
  `checkout` confirma a reserva, nunca debita estoque direto.
- Quantidade por linha do carrinho: 1..10 (`MAX_QTY_PER_LINE`).
