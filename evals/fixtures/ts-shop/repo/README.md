# shop

Monorepo npm workspaces:

| Workspace | Path | What |
|---|---|---|
| `@shop/shared` | `packages/shared` | domain contracts: `Sku`, `Cart`, `Order`, `OrderStatus`, prices in integer cents |
| `@shop/api` | `packages/api` | HTTP api (express): catalog, inventory (stock + reservations), orders/checkout |
| `@shop/web` | `apps/web` | storefront (React + Vite) |

```
npm ci
npm test            # node:test in every workspace (no build step: node strips TS types)
npm run lint        # eslint flat config
npm run typecheck   # tsc -b
npm run e2e         # Playwright end-to-end suite against a local api + web
```

Node >= 22.18 is required (type stripping on by default). Only erasable TypeScript syntax is
allowed in `packages/*` (no `enum`, `namespace`, parameter properties).
`packages/api/test/fixtures/legacy-erp/` holds sample exports of the old ERP (Python/Java) used only
as import test data.
