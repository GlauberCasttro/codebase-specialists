# 03-TASK-QA — Portão, oráculo e o fechamento real da win-motor-copia

id: 03-TASK-QA
feature: win-bash
tipo: QA
grupo: —
agente: QA (fase fechamento do /e2e-loop)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: 02-TASK-BASH (o bash_exe é o que se mede)
status: PENDENTE
gate: PENDENTE

## Goal
Rodar o portão em cópia limpa (WSL, 2 Pythons POSIX) com o oráculo da feature, o oráculo no Windows nativo (Git Bash e
PowerShell, sem `PYTHONUTF8`) e, como prova de ponta a ponta, `feature.py fechar check win-motor-copia` com o
`feature.py` da cópia. NÃO corrigir nada.

## Contexto
CA-01..CA-05; critério de parada do FEATURE.md (5/5 nos dois ambientes; `fechar check win-motor-copia` ok no Windows).

## Subtasks
1. Portão (WSL) com `--src` da cópia e o oráculo `campanhas/win-bash/oraculo:test_win_bash`.
2. Oráculo no Windows nativo pelos 2 shells; `fechar check win-motor-copia` rodando o `feature.py` da cópia.
3. Matriz CA a CA no Handoff.

## Invariants
- Nada é editado por esta task além do próprio Handoff.

## Scope IN / OUT
IN: medição. OUT: correção.

## Arquivos permitidos
- `.claude/state/features/win-bash/TASKS/03-TASK-QA.md`

## AC
- `portao.out` em `RESULTADO: VERDE` + `FIM`; oráculo 5/5 no Windows nos 2 shells; `fechar check win-motor-copia` ok.

## DoD
- Handoff com os números CA a CA.

## Verificação
```bash
bash .claude/tools/portao.sh win-bash --oraculo campanhas/win-bash/oraculo:test_win_bash --lista local/portao-win-bash.lista
```

## Handoff
