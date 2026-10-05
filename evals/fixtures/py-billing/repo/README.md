# billing

Serviço de faturamento da Acme: **faturas** (`src/billing/invoices`), **pagamentos**
(`src/billing/payments`) e **ledger** de partidas dobradas (`src/billing/ledger`), com tipos comuns
em `src/billing/shared` (`Money` em centavos, erros, relógio injetável).

## Rodar
```
uv sync          # instala dependências pinadas (uv.lock)
make test        # PYTHONPATH=src python3 -m unittest discover -s tests -v
make lint        # check-money + ruff check + ruff format --check
```

Cliente HTTP do gateway: httpx 0.26.0 (pinado em uv.lock).
Testes usam `unittest` da stdlib. Decisões em `docs/adr/`.
`tests/fixtures/` contém amostras de sistemas legados (um .csproj e um package.json de exportação)
usadas só como dados de importação — não são parte do serviço.
