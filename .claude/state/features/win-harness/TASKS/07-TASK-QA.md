# 07-TASK-QA — Portão e oráculo, CA a CA, no Windows nativo e no WSL

id: 07-TASK-QA
feature: win-harness
tipo: QA
grupo: —
agente: QA (fase fechamento do /e2e-loop)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14
depends: 06-TASK-SUITE-HARNESS-DEV (é a última correção; depende transitivamente de 02–05)
status: IN_PROGRESS
gate: FAIL

## Goal
Rodar o portão da feature (cópia limpa = HEAD + só os arquivos da feature) com o oráculo congelado, no Windows nativo
sem atalho (suíte harness-dev + oráculos) e no WSL (régua completa), e montar a matriz CA → evidência. NÃO corrigir
nada: falha volta ao corretor com a evidência.

## Contexto
Os 14 CAs do FEATURE.md; critério de parada (14/14 nos dois ambientes; harness-dev 0 falhas; oráculos win-bash e
win-motor-copia verdes; 0 `def` removido). As suítes do produto no Windows nativo são da B-14: aqui só no WSL.

## Subtasks
1. Portão no Windows nativo: `--suites harness-dev` + os 3 oráculos, com a lista de arquivos da feature.
2. Portão completo no WSL com os mesmos oráculos.
3. Matriz CA → comando → resultado nos dois ambientes; `def` removido = 0; privacidade.

## Invariants
- O oráculo não muda (`oracle verify`). Só entra no relatório o que foi executado.

## Scope IN / OUT
IN: execução e relatório. OUT: qualquer mudança de código ou de teste.

## Arquivos permitidos
- `.claude/state/features/win-harness/TASKS/07-TASK-QA.md`

## AC
- Portão `RESULTADO: VERDE` + `FIM` nos dois ambientes; matriz com os 14 CAs verdes.

## DoD
- Handoff com a matriz e os caminhos dos `portao.out`; Aceite QA proposto.

## Verificação
```bash
bash .claude/tools/portao.sh win-harness --suites harness-dev --oraculo campanhas/win-harness/oraculo:test_win_harness --oraculo campanhas/win-bash/oraculo:test_win_bash --oraculo campanhas/win-motor-copia/oraculo:test_win_motor_copia --lista local/portao-win-harness.lista
```

## Handoff
- QA: general-purpose · sonnet (23 turnos), instância que não executou nada na feature → ACCEPT.
- Portão Windows nativo (`--suites harness-dev --pythons python`, 3 oráculos; `local/qa-win-harness/portao-windows.out`):
  Python 3.12.7 — harness-dev 108 OK (1 skip symlink); test_win_harness 55 OK (5 skips só-POSIX); test_win_bash 18 OK;
  test_win_motor_copia 21 OK; RESULTADO: VERDE · FIM.
- Portão completo WSL (`local/qa-win-harness/portao-wsl.out`): 16 suítes do produto + evals + harness-dev 108 + 3 oráculos,
  todas OK em python3 e /usr/bin/python3 (3.10.12); skips iguais à linha de base (harness 16, scan 1, upgrade 7; oráculos
  só-Windows); RESULTADO: VERDE · FIM. Nenhum `def` removido, nenhum termo privado (portão).
- Conferência do tech-lead: as duas saídas lidas (sem FAILED/SEM RESULTADO/REMOVIDA/PRIVADO); `oracle verify` intacto;
  snapshot: a QA não escreveu na cópia (só ruído `evals/**/obj/` do IDE) nem no projeto.
- Matriz: CA-01..05, 07, 08, 10..12 PASS no Windows (só-Windows); CA-06, CA-09 PASS nos dois; CA-13 PASS (Windows,
  harness-dev 108 + TestCA13); CA-14 PASS (WSL, harness-dev + win-bash + win-motor-copia nos 2 Pythons).
- Limites: o portão imprime o total do oráculo, não o resultado por classe (0 falhas/erros em 55 nos dois); um Python por
  ambiente (Windows `python`; WSL python3 = /usr/bin/python3, mesmo 3.10.12); PATH real dos hooks no Claude Code e macOS
  não medidos.
