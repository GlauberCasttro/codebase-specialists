# Notas do time de billing para agentes

- Fale com a Carla (contabilidade) antes de mexer no plano de contas em `src/billing/ledger/accounts.py`.
- Fechamento mensal roda no dia 1 às 03h: não faça deploy de payments entre dia 28 e dia 2.
- Toda mudança em valor monetário precisa de um teste com centavo "quebrado" (ex.: 99999 cents).
