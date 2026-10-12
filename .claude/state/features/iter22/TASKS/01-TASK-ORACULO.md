# 01-TASK-ORACULO — Oráculo da iter22 (CA-01..CA-04), escrito por agente separado

id: 01-TASK-ORACULO
feature: iter22
tipo: ORACULO
grupo: —
agente: oraculista (rh; agente separado que nunca vê a cópia do corretor)
CA: CA-01, CA-02, CA-03, CA-04
depends: —
status: DONE
gate: PASS

## Goal
ESPEC.md + test_iter22.py (+ medir.py, base.txt) em `campanhas/iter22/oraculo/` que FALHAM no HEAD 0.12.0 e passam
com a entrega. O `show` tem de ser exercitado PELO hook pre-bash (é o buraco do F2). NÃO tocar produto.

## Contexto
CA-01..CA-04. Âncoras: guard.py:262-267 (STATE_SUB), :330 e :345 (recusas); helper de hook pre-bash em
scripts/harness/tests/test_autonomy_install.py:104; catálogo references/migrations.json5:25,95.

## Subtasks
1. Fixture de alvo instalado com hook pre-bash e uma task; payload de Bash do principal e de subagente.
2. CA-03: varredura argparse × guard que falha com subcomando fictício sem regra (mutação calibrada).
3. CA-04: upgrade de um alvo 0.12.0 (git archive do HEAD) para a cópia; oráculos anteriores intactos.
4. Calibrar: base no HEAD (falha pelo motivo certo) e saída vazia; o tech-lead congela.

## Invariants
- Oráculo só em `campanhas/iter22/oraculo/`; quem testa não constrói.

## Scope IN / OUT
IN: oráculo. OUT: qualquer arquivo de produto.

## Arquivos permitidos
- `campanhas/iter22/oraculo/ESPEC.md`
- `campanhas/iter22/oraculo/test_iter22.py`
- `campanhas/iter22/oraculo/medir.py`
- `campanhas/iter22/oraculo/base.txt`

## AC
- 4 CAs com teste; base no HEAD medida (falha por asserção) e registrada em base.txt.

## DoD
- Oráculo congelado (`oracle freeze` com todos os arquivos); Handoff preenchido.

## Verificação
```bash
cd campanhas/iter22/oraculo && python3 medir.py
```

## Handoff
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus), agente separado (não leu local/work).
- Entregue: ESPEC.md, test_iter22.py (9 testes: 6 D, 3 R; show exercitado PELO hook pre-bash instalado no alvo),
  medir.py, base.txt. CA-04 monta o alvo 0.12.0 por `git archive 7fdb431` (ou $CS_OLD_SKILL_DIR).
- Medido pelo tech-lead no HEAD d2e07ff: 3/9 (D 0/6, R 3/3), idêntico em python3 3.13 e /usr/bin/python3 3.9; motivo
  de cada D: "cs-state show desconhecido", "subagente não roda cs-state show", ['show'] != [], VERSION 0.12.0 < 0.12.1,
  plano "nada a fazer", docstring antiga.
- Calibração (oraculista, cópias em mktemp): correção mínima ⇒ 9/9 nos 2 Pythons; mutação CA-03 (subparser fictício
  sem regra) ⇒ FAIL. Congelado: `oracle freeze` 524416ebaf44 (4 arquivos); oracle verify intacto.
- Lacunas declaradas: CA-02 sem delegação em voo (o guard decide pelo subcomando); docstring testada por heurística de
  texto; CA-03 detecta "sem regra" pela palavra "desconhecido".
