# Limites honestos (não alegue o que não existe)

## O motor (`ac.py`, cópia embutida) não faz

- Não despacha subagentes nem roda o oráculo ou as suítes: `oracle.calibration`, `integration.tests_green`,
  `decision` e `report` são **declarados** por você com `set`; o motor confere presença e coerência, não verdade.
- Não roda git: o portão `commit` registra autorização; não impede um commit feito fora dele.
- Não confere que a frente escreveu só no seu `escreve` (o `plan check` valida o plano, não o diff — quem confere o
  diff é o portão + `conferir-commit.sh` + o `/revisor`).
- Orçamento: só `max_rounds` é aplicado (no `round new`); `max_hours`/`max_parallel` são informativos; "2 rodadas sem
  progresso → escalar" é julgamento seu.
- `results compare` faz a média de todas as configs não-baseline juntas: decida pelas linhas, não pela média.

## Defeitos conhecidos do motor (abertos no projeto auto-correcao, v0.5)

| Id | Defeito | Como conviver aqui |
|---|---|---|
| AC-08 | `oracle change` re-hasheia o disco e absorve edição indevida | confira o diff dos arquivos do oráculo desde o freeze antes |
| AC-09 | `run record` no mesmo segundo do `done correcao` é recusado | registre de novo |
| AC-10 | `round new` abriu rodada com remedicao/decisao abertas | confira `status` antes do `round new` |
| AC-12 | `set scope` muda o escopo depois do portão, sem evento | não use; escopo novo = frente nova ou founder |
| AC-13 | o hook nega comando legítimo com variável + palavra de aprovação | caminho literal sempre |
| — | trocar o critério de parada não invalida o portão `stop` | critério novo ⇒ peça novo script de aprovação |

Corrigir o motor é trabalho do projeto `auto-correcao`; aqui só se atualiza a cópia (`ac/ORIGEM.txt`).

## O harness

- `guard-entrega.py` só vê Edit/Write/MultiEdit/NotebookEdit; escrita por Bash no produto não é bloqueada (a regra
  vale por escrito; `portar.sh` usa Bash de propósito).
- `guard-git.sh` e `hook_aprovacao.py` são filtros sintáticos, não sandbox.
- O ledger de cada campanha (`campanhas/*/.auto-correcao/`) é local: numa máquina nova só existem os oráculos.
- O portão mede suítes, oráculos e remoção de `def` — não qualidade de uso real. Uso real = medição separada,
  com custo confirmado pelo founder.
- A régua do carimbo (GATE) só diz que o produto vivo é exatamente o que um portão VERDE (ou o `/e2e-loop`)
  testou; não diz que o teste é bom (L20).
