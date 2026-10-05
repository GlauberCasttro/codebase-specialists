# ADR 0001 — Migrações são append-only

- Status: aceito (2025-02-12)

## Contexto
Em janeiro alguém editou `0002_delivery_status_enum.up.sql` já aplicada em produção para incluir um
status; staging e produção divergiram e o deploy seguinte falhou no meio.

## Decisão
- Migração aplicada **nunca** é editada. `deploy/migrate.sh` grava o sha256 de cada arquivo e aborta
  se um arquivo aplicado mudar.
- Novo valor de enum = nova migração com `ALTER TYPE delivery_status ADD VALUE`.
- Os valores de `DeliveryStatus` em `internal/dispatch/status.go` espelham o enum `delivery_status`.
- Down migrations existem para dev; **nunca** rodam em produção (`deploy/rollback.sh` só troca imagem).
- Timestamps são `timestamptz` gravados em UTC.
