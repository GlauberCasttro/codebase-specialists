# 02-TASK-BASH — bash_exe() no feature.py e conferir_commit usando-a

id: 02-TASK-BASH
feature: win-bash
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
Criar `bash_exe()` em `.claude/tools/feature.py` (Windows: `shutil.which("bash")` descartando
`%SystemRoot%\System32` sem diferenciar caixa; senão o `bash.exe` do Git a partir de `shutil.which("git")` —
`<raiz>\bin\bash.exe` ou `<raiz>\usr\bin\bash.exe`; senão `Recusa` citando o Git Bash; fora do Windows: `"bash"`) e
usá-la em `conferir_commit` (`:548`) no lugar de `"bash"`. Testes unitários dela em `test_feature.py`. NÃO mover para
`estado_lib.py`, NÃO tocar as outras chamadas nem os outros tools, NÃO mudar a assinatura de `conferir_commit`.

## Contexto
CA-01..CA-05. Âncoras: `.claude/tools/feature.py:544-550`, `:53` (`Recusa`), imports `:35-42` (já tem `shutil`);
E2 F1 (WSL no gate), F2 (`which` acha o Git Bash).

## Subtasks
1. Rodar o oráculo congelado e ver os 5 CAs falharem (RED).
2. Escrever `bash_exe()` e trocar a chamada em `conferir_commit`; testes unitários em `test_feature.py`.
3. Rodar o oráculo, `test_feature.py` e a suíte harness-dev no Windows e no WSL (GREEN).

## Invariants
- `conferir_commit` mantém assinatura e retorno `(ok, saida)`; nenhum `def` removido.
- macOS/Linux: o comando executado continua `bash <script> …`.

## Scope IN / OUT
IN: `bash_exe()`, a chamada em `conferir_commit`, testes. OUT: demais chamadas, demais tools, `estado_lib.py` (B-15).

## Arquivos permitidos
- `.claude/tools/feature.py`
- `.claude/tools/tests/test_feature.py`

## AC
- Os 5 CAs do oráculo verdes no Windows nativo e no WSL; `test_feature.py` verde; harness-dev sem falha nova.

## DoD
- Régua da task verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -v
```

## Handoff
