# ADR 0001 — Valores monetários em centavos inteiros

- Status: aceito (2025-03-04)
- Decisores: Ana Ribeiro (tech lead), Bruno Tavares (financeiro)

## Contexto
Em 2024 o importador de faturas somava `float` e o fechamento mensal divergiu R$ 0,03 do
extrato do gateway em 1.200 faturas. A auditoria exige conciliação ao centavo.

## Decisão
Todo valor monetário é um `int` de **centavos** dentro de `billing.shared.money.Money`.
`float` nunca entra no domínio: `Money(10.5)` levanta `InvalidAmount`. Percentuais (ISS) são
inteiros em *basis points* (1% = 100 bp) e o arredondamento é **half-even**, feito uma única vez
em `Money.percent`. Rateios usam `Money.allocate` (maior resto), que nunca perde centavo.

## Consequências
- `make check-money` (scripts/check_no_float_money.py) falha o lint se aparecer `float(`,
  `round(` ou divisão `/` sobre `cents` em `src/billing`.
- Na fronteira (gateway HTTP, CSV) o valor trafega como `amount_cents` inteiro.
- Exibição formata com `Money.format()`; nunca converter para decimal para somar.
