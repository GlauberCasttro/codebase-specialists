# ADR 0001 — web só fala com a api por HTTP; contratos em @shop/shared

- Status: aceito (2025-04-22)

## Contexto
Um PR fez `apps/web` importar `@shop/api/inventory` para "economizar uma chamada". O bundle passou a
carregar express e a regra de reserva rodou no browser, com relógio do cliente. Foi revertido.

## Decisão
`apps/web` nunca importa `@shop/api`. Tipos e contratos (`Sku`, `Cart`, `Order`, `OrderStatus`,
`priceCents`) vivem em `@shop/shared`. A regra é lint (`no-restricted-imports` em eslint.config.mjs).
