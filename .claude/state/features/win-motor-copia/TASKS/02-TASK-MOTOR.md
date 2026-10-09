# 02-TASK-MOTOR — Copiar o motor de 30e2da6, reaplicar o layout, ORIGEM e eol=lf

id: 02-TASK-MOTOR
feature: win-motor-copia
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-01, CA-02, CA-04, CA-05
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: DONE
gate: PASS
complexidade: normal

## Goal
Substituir `ac.py`, `frase.py` e `hook_aprovacao.py` de `.claude/tools/ac/` pelos de `auto-correcao@30e2da6`,
reaplicar no `ac.py` as 2 linhas do layout embutido (procurar `references/` ao lado do `ac.py`), regravar o
`ORIGEM.txt` (commit `30e2da6`, sha256 de origem e embutido dos 7 arquivos, explicação da única diferença) e criar o
`.gitattributes` com `.claude/tools/ac/** text eol=lf`. NÃO editar a lógica do motor, NÃO mexer em `references/`
(iguais na fonte), NÃO estender o `.gitattributes` ao repositório inteiro (B-15), NÃO tocar `.claude/settings.json`.

## Contexto
CA-01, CA-02, CA-04, CA-05. Âncoras: F1 `frase.py:187-239`, F2 `ac.py:952`, F4 `test_harness_dev.py:451`, F5
`30e2da6:scripts/ac.py:35`; as 2 linhas atuais estão logo depois de `CICLO = ...` no `ac.py` embutido.

## Subtasks
1. Rodar o oráculo congelado e ver CA-01/02/04 falharem (RED).
2. Copiar os 3 arquivos da fonte (bytes LF), reaplicar as 2 linhas no `ac.py`, regravar o `ORIGEM.txt`.
3. Criar `.gitattributes` (uma regra) e conferir que os arquivos do motor ficam LF na cópia de trabalho.
4. Rodar o oráculo, `test_harness_dev.MotorEmbutido` e a suíte harness-dev (GREEN, sem falha nova).

## Invariants
- O `ac.py` difere da fonte só pelas 2 linhas; `frase.py` e `hook_aprovacao.py` idênticos à fonte.
- Nenhum `def` removido; a frase nunca é impressa nem pedida.

## Scope IN / OUT
IN: 3 arquivos do motor, ORIGEM.txt, `.gitattributes`. OUT: `references/`, `settings.json` (03), demais tools (B-15).

## Arquivos permitidos
- `.claude/tools/ac/ac.py`
- `.claude/tools/ac/frase.py`
- `.claude/tools/ac/hook_aprovacao.py`
- `.claude/tools/ac/ORIGEM.txt`
- `.gitattributes`

## AC
- CA-01, CA-02, CA-04 e CA-05 do oráculo verdes no Windows nativo e no WSL; `MotorEmbutido` inteira verde.

## DoD
- Régua da task verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA01 -k CA02 -k CA04 -k CA05
```

## Handoff
- Executor real: subagente general-purpose, model sonnet (roteador: executor ciclo 1). Arquivos (na cópia):
  `.claude/tools/ac/ac.py` (fonte `30e2da6` + 2 linhas do layout, linhas 36–37), `frase.py` e `hook_aprovacao.py`
  (idênticos à fonte), `ORIGEM.txt` (30e2da6; 7+7 sha256; só o ac.py difere), `.gitattributes` (1 regra). Os 4
  `references/*.json5` já estavam em LF e iguais à fonte (não mudaram).
- Conferência do tech-lead: escopo por snapshot = só os arquivos permitidos (+ settings.json da 03; `obj/` da fixture
  .NET é ruído de build da IDE, fora do commit); projeto vivo intacto fora do estado; oráculo inteiro contra a cópia
  Windows 3.12 sem PYTHONUTF8 `Ran 21 · OK`, WSL `Ran 21 · OK`; selftest 135/135; 0 `def` removido; privacidade 0.
- Régua completa (e2e.py, WSL, python3 e /usr/bin/python3): 15 de 17 suítes PASS de primeira; `harness` (2 erros) e
  `scan` (5 falhas) eram IDÊNTICAS no HEAD — causa: `make` ausente no WSL (FileNotFoundError 'make'; `make test`
  unavailable). Founder instalou o `make`; rerodadas HEAD × cópia: `harness` 306 OK (16 skips) e `scan` 90 OK nas duas.
- Executor declarou BLOCKED por `test_help_e_init_com_ciclo_embutido` (UnicodeDecodeError no Windows sem PYTHONUTF8):
  PRÉ-EXISTENTE (mesmo erro no HEAD; helper `run()` de test_harness_dev.py:32 decodifica UTF-8 estrito) → B-15.
- Revisor pontual isolado: general-purpose · opus · APPROVED (CA-01/02/04/05 PASS). Ressalvas MENOR: (1)
  `carimbo.sh:40-41` subconta etapas no Windows (✓ vira `✓`) — PRÉ-EXISTENTE, B-15; (2) `ac.py:174-175` hash
  neutro a CRLF faria reprovar oráculo antigo congelado com bytes CRLF no Windows — SUSPEITA, sem caso nesta máquina.
