Crie e altere itens só com `.swarm/bin/cs-state new ...` (`new epico|feature|story|sprint|task`; avulsa: `cs-state add task`); o board nunca é editado à mão (o validador detecta pela cadeia de hashes).
- US: "Como <papel>, quero <ação>, para <valor>" + critérios Gherkin, cada um ligado a um teste.
  Ex.: `.swarm/bin/cs-state new story --tipo US --feature FEA-003 --agents <agente> --title "2ª via do boleto" --como cliente --quero "2ª via do boleto" --para "pagar após o vencimento" --allowed-path <arquivo> --verify-cmd "<teste>" --criterio "AC-1|Dado boleto vencido Quando peço 2ª via Então recebo novo vencimento|<teste>"`
- Bug: passos de reprodução + teste que falha hoje + severidade + ambiente; sem o teste vermelho não vira READY.
  Ex.: `.swarm/bin/cs-state new story --tipo BUG --feature FEA-003 --agents <agente> --title "Total ignora cupom" --reproducao "<passos>" --teste <teste-que-falha> --allowed-path <arquivo> --verify-cmd "<teste>"`
- Fix: `fixes:` aponta o BUG, achado de review ou de forense + teste que prova.
  Ex.: `.swarm/bin/cs-state new story --tipo FIX --fixes BUG-7 --feature FEA-003 --agents <agente> --title "Aplicar cupom antes do frete" --teste <teste> --allowed-path <arquivo> --verify-cmd "<teste>"`
- Critério vira teste no brief: `{id: "AC-1", criterion: "Dado boleto vencido, Quando peço 2ª via, Então recebo novo vencimento", verified_by: "test:tests/test_boleto.py::test_segunda_via"}`; o que não dá para provar executando leva `verified_by: "reviewer"`.
