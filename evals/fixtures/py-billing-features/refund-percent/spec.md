# FEAT refund-percent — Reembolso percentual

**Como** analista de suporte **quero** reembolsar um percentual do valor capturado de um pagamento
**para** atender acordos de desconto pós-venda sem calcular centavos na mão.

## Regras
1. `PaymentService.refund_percent(payment_id: str, basis_points: int) -> Payment`.
2. O valor reembolsado é `captured.percent(basis_points)` — basis points (1% = 100 bp), arredondamento
   half-even feito por `Money.percent` (ADR 0001). Nada de float.
3. `basis_points` precisa ser `int` entre 1 e 10000; qualquer outra coisa (float, bool, 0, >10000)
   levanta `InvalidAmount`.
4. Respeita o limite de reembolso: o valor não pode exceder `capturado - já reembolsado`
   (`RefundExceedsCapture`); quando recusa, não chama o gateway e não lança nada no ledger.
5. Cada reembolso aceito lança no ledger como o reembolso comum (débito REVENUE, crédito CASH).

## Critérios de aceite (executáveis)
`PYTHONPATH=src python3 -m unittest discover -s tests/acceptance` — arquivo
`tests/acceptance/test_refund_percent.py` (aprovado; não pode ser alterado).
