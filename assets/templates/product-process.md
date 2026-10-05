Crie e altere itens só com `.swarm/bin/cs-state add ...`; o board nunca é editado à mão (o validador detecta pela cadeia de hashes).
- US: "Como <papel>, quero <ação>, para <valor>" + critérios Gherkin, cada um ligado a um teste.
  Ex.: `.swarm/bin/cs-state add story --type us --feature FEAT-3 --title "Como cliente, quero 2ª via do boleto, para pagar após o vencimento"`
- Bug: passos de reprodução + teste que falha hoje + severidade + ambiente; sem o teste vermelho não vira READY.
  Ex.: `.swarm/bin/cs-state add story --type bug --feature FEAT-3 --title "Total ignora cupom" --severity alta`
- Fix: `fixes:` aponta o BUG, achado de review ou de forense + teste que prova.
  Ex.: `.swarm/bin/cs-state add story --type fix --fixes BUG-7 --title "Aplicar cupom antes do frete"`
- Critério vira teste no brief: `{id: "AC-1", criterion: "Dado boleto vencido, Quando peço 2ª via, Então recebo novo vencimento", verified_by: "test:tests/test_boleto.py::test_segunda_via"}`; o que não dá para provar executando leva `verified_by: "reviewer"`.
