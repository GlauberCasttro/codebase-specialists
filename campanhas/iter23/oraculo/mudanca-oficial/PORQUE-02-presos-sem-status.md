# Mudança oficial 02 — itens presos: igualdade sem o campo canônico `status`

Decisão do founder: **D-39** (2026-10-16). Teste afetado: `TestCA08.test_ca08_apply_relata_itens_presos_sem_alterar`.
Patch: `02-presos-sem-status.patch`.

## O que muda

Antes, o teste exigia que o arquivo JSON de cada item preso fosse igual BYTE A BYTE antes e depois do
`upgrade --apply`. A 0.13.1 (iter25, CA-05 aprovado) grava o campo canônico `status` em TODOS os itens (D-37), o que
quebraria a igualdade de bytes sem que o item tenha sido de fato alterado.

Agora "não alterar os itens presos" significa:

- o arquivo continua no MESMO caminho (se sumiu ou mudou de lugar, falha);
- o JSON depois, sem as chaves `status` e `_generated_by` (cabeçalho que o motor grava), é IGUAL ao de antes, sem
  as mesmas chaves;
- se `status` existir depois, tem de ser código do vocabulário canônico: `TODO`, `BACKLOG`, `ACTIVE`, `DONE`,
  `DROPPED` ou o par `<STATUS>/<DELEG>`;
- JSON inválido depois falha. Igualdade de bytes continua passando direto.

Nada mais muda neste teste nem em outros.

## Por que não enfraquece

O item preso continua sem poder mudar de lugar nem de conteúdo: título, critérios, estado de execução, vínculos e
qualquer outro campo seguem comparados por inteiro. A única tolerância é ganhar o campo canônico `status` (e o
cabeçalho gerado), e mesmo esse campo é validado contra o vocabulário fechado. O upgrade não ganha licença para
"destravar" ou reescrever o item; ganha apenas a normalização que a D-37 exige em todos os itens.
