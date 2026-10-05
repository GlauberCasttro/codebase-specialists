# ADR 0002 — Ledger append-only com estorno

- Status: aceito (2025-04-11)
- Decisores: Ana Ribeiro, Carla Mendes (contabilidade)

## Contexto
Um "delete de lançamento rascunho" foi mergeado e revertido no mesmo dia: apagar lançamento
quebra a trilha de auditoria exigida pelo contador e esconde erro de conciliação.

## Decisão
`billing.ledger.journal.Journal` só tem `post` e `reverse`. Não existe `update` nem `delete`.
Todo `LedgerEntry` é balanceado (soma de débitos == soma de créditos, em centavos) e é corrigido
apenas por um lançamento de estorno (`reverse`), que pode ocorrer uma única vez por lançamento.
Postings nunca são negativos.

## Consequências
- Testes garantem que `Journal` não tem `delete`/`update` (tests/test_ledger.py).
- O plano de contas (`ledger/accounts.py`) não é renumerado.
