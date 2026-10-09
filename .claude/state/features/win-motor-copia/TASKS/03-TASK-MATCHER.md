# 03-TASK-MATCHER — Hook de aprovação do projeto vigia também a ferramenta PowerShell

id: 03-TASK-MATCHER
feature: win-motor-copia
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-03
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: DONE
gate: PASS
complexidade: baixa

## Goal
Trocar, em `.claude/settings.json`, o matcher do registro PreToolUse do `hook_aprovacao.py` de `Bash` para
`Bash|PowerShell`. NÃO mudar o comando do hook (o `python3` é da B-15), NÃO mexer nos outros registros (guard-git,
guard-entrega, guard-estado, exige-modelo, SessionStart), NÃO reformatar o arquivo.

## Contexto
CA-03. Âncora: `.claude/settings.json:15` (`"matcher": "Bash"` do registro cujo comando cita
`.claude/tools/ac/hook_aprovacao.py`); achado F3 da E2.

## Subtasks
1. Rodar o teste CA03 do oráculo e ver a parte do matcher falhar (RED).
2. Alterar só aquele matcher; validar o JSON.
3. Rodar CA03 (a parte do selftest depende da 02) e a suíte harness-dev (GREEN no matcher).

## Invariants
- O JSON continua válido; os outros 5 registros ficam byte a byte iguais.

## Scope IN / OUT
IN: um matcher em `.claude/settings.json`. OUT: o comando do hook, os demais hooks, o motor (02).

## Arquivos permitidos
- `.claude/settings.json`

## AC
- A parte de matcher do CA-03 verde; `python -c "import json;json.load(open('.claude/settings.json'))"` sai 0.

## DoD
- Régua da task verde; diff de uma linha; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA03
```

## Handoff
- Executor real: subagente general-purpose, model haiku (roteador: complexidade baixa válida). Arquivo:
  `.claude/settings.json` da cópia — linha 15 `"matcher": "Bash"` → `"Bash|PowerShell"` (registro do
  `hook_aprovacao.py`); os outros 5 registros intactos.
- Conferência do tech-lead: diff HEAD × cópia = só a linha 15; JSON válido; privacidade 0; oráculo inteiro contra a
  cópia `Ran 21 · OK` (Windows e WSL), incluindo CA-03 completo (matcher + decide PowerShell + selftest 135).
- Régua: a mesma da 02 (completa; `harness`/`scan` verdes depois do `make` no WSL, idênticas ao HEAD).
- Revisor pontual isolado: general-purpose · sonnet · APPROVED, sem findings. Lacuna dele (matcher sem teste ao
  vivo) já tem evidência nesta máquina: na prova da win-hook (2026-10-08), uma sessão `claude -p` com matcher
  `Bash|PowerShell` disparou `PreToolUse:PowerShell` e negou o gate.
