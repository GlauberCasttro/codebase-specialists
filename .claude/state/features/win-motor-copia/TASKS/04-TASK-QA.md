# 04-TASK-QA — Portão e oráculo, CA a CA, nos dois ambientes

id: 04-TASK-QA
feature: win-motor-copia
tipo: QA
grupo: —
agente: QA (fase fechamento do /e2e-loop)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: 02-TASK-MOTOR (o motor copiado é o que se mede), 03-TASK-MATCHER (o matcher completa o CA-03)
status: DONE
gate: PASS

## Goal
Rodar o portão em cópia limpa (WSL: 2 Pythons POSIX) com o oráculo da feature e conferir cada CA no Windows nativo
(Git Bash e PowerShell, sem `PYTHONUTF8`). NÃO corrigir nada: falha volta para a task dona.

## Contexto
CA-01..CA-05; critério de parada do FEATURE.md (5/5 nos dois ambientes, harness-dev sem falha nova, selftest > 83).

## Subtasks
1. Portão: `bash .claude/tools/portao.sh win-motor-copia --oraculo campanhas/win-motor-copia/oraculo:test_win_motor_copia --lista <arquivos das 02/03>` (WSL).
2. Oráculo no Windows nativo pelo Git Bash e pelo PowerShell, sem `PYTHONUTF8`.
3. Registrar CA a CA (passou/falhou, com a saída) no Handoff.

## Invariants
- Nada é editado por esta task além do próprio Handoff.

## Scope IN / OUT
IN: medição. OUT: qualquer correção.

## Arquivos permitidos
- `.claude/state/features/win-motor-copia/TASKS/04-TASK-QA.md`

## AC
- `portao.out` termina em `RESULTADO: VERDE` + `FIM`; oráculo 5/5 no Windows nativo nos 2 shells.

## DoD
- Handoff com os números CA a CA.

## Verificação
```bash
bash .claude/tools/portao.sh win-motor-copia --oraculo campanhas/win-motor-copia/oraculo:test_win_motor_copia --lista local/portao-win-motor-copia.lista
```

## Handoff
- QA real: subagente general-purpose · model sonnet (roteador: qa). VEREDITO: ACCEPT.
- Portão (WSL, cópia limpa = HEAD e8a9b93 + 6 arquivos, python3 e /usr/bin/python3 = 3.10.12):
  `local/portao-win-motor-copia/portao.out` → `RESULTADO: VERDE` + `FIM` (conferido pelo tech-lead). Suítes nos 2
  Pythons: cslib 17, doctests 19, emit 55, facts 6, harness 306 (16 skips de base), interview 8, memory 14, panel 11,
  probes 78, sanitize 8, scan 90 (1 skip), stage 51, team 61, upgrade 8 (7 skips), verify 13, evals 10, harness-dev
  76; oráculo test_win_motor_copia 21 OK.
- Windows nativo (sem PYTHONUTF8), oráculo contra a cópia: Git Bash (Python 3.12) 21/21 OK; PowerShell 5.1 21/21 OK.
  `oracle verify` intacto.
- Matriz: CA-01..CA-05 PASS nos 3 ambientes (WSL portão, Win Git Bash, Win PowerShell).
- Limites: o QA não rodou a suíte completa do produto no Windows nativo (fora da task; B-14/B-15); skips iguais nos
  2 Pythons, não comparados com portão anterior. Tech-lead conferiu por snapshot que o QA não escreveu na cópia.
