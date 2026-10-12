# HISTORICO — feature iter22

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-12T14:54:10-0300 — Abertura da feature iter22
- campanha: campanhas/iter22 (ac.py init; escopo: scripts/harness/engine/guard.py, scripts/harness/tests/test_iter22_*.py, references/migrations.json5, docs/09-upgrade.md, VERSION, README.md)
- tasks: 5 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — Investigação medida
    
    ## Inventário
    - `python3 scripts/harness/engine/state.py --help` → 48 subcomandos de nível superior no argparse do cs-state.
    - `scripts/harness/engine/guard.py:262-267` → STATE_SUB["main"] com 42 nomes, STATE_SUB["any"] (leitura do subagente)
      com 9 (board, brief, check, find, next, status, tree, validate, why).
    - `scripts/harness/engine/guard.py:311-345` (harness_call_problem) → regras explícitas para legacy-ack, waive-verify
      (atos do humano), dispatch (via Agent), submit/review/abstain (atos do subagente).
    - `python3 scripts/memory/mem.py --help` → 11 subcomandos do cs-mem; o guard não filtra cs-mem por subcomando
      (nenhum STATE_SUB equivalente para mem em guard.py).
    
    ## Classificação
    - argparse (48) = 42 em STATE_SUB["main"] + 5 com regra explícita (legacy-ack, waive-verify, submit, review,
      abstain) + 1 SEM nada: `show`. Soma 48. Nenhum nome do guard sem subcomando no argparse (0).
    - muda: `show` entra em STATE_SUB["main"] e em STATE_SUB["any"] (é leitura). não muda: os 47 restantes. congelado:
      oráculos iter16/18/19/20/21.
    
    ## Exclusões
    - cs-mem, cs-session, cs-route: fora (o guard não lista subcomandos deles; nenhuma regressão relatada).
    - O que o `show` exibe (B-33), add→new (B-28), órfãs (B-19), caderno duplicado (B-36), retract com id curto (B-37).
    - Motor embutido do harness de desenvolvimento (`.claude/tools/ac/`).
    
    ## Achados
    - F1 — `scripts/harness/engine/guard.py:330` — `return None if sub in STATE_SUB["main"] or sub is None else
      "cs-state %s desconhecido" % sub`: `show` (state.py, iter19) nunca foi adicionado a STATE_SUB ⇒ o agente
      principal recebe "cs-state show desconhecido" (uso real na cobaia .NET, 2026-10-12) e o subagente cai na linha
      345 ("subagente não roda cs-state show").
    - F2 — `scripts/harness/tests/test_iter19_estado.py` e `campanhas/iter19/oraculo/test_iter19.py` chamam o
      `cs-state show` direto (0 ocorrências de `pre-bash`/hook junto de `show` no oráculo iter19) ⇒ nenhum teste passa o
      show pelo guard; por isso oráculo e portão ficaram verdes. Existe o helper `hook(root, "pre-bash", …)` em
      `scripts/harness/tests/test_autonomy_install.py:104` e `test_escalada_saidas.py:268,353`.
    - F3 — a lista STATE_SUB é escrita à mão, separada do argparse (`guard.py:262` × `state.py`): nada impede o próximo
      subcomando novo de repetir o F1.
    - F4 — `scripts/harness/engine/guard.py:104-105`: a docstring de `notebook_text_problems` ainda diz "bloco
      desatualizado mas com selo íntegro também não [é adulteração]", contrário ao comportamento entregue na iter21
      (bloco aceito só se igual ao render do cs-mem).
    - F5 — `references/migrations.json5:25,95`: última versão 0.12.0; sem entrada 0.12.1 o upgrade dos alvos não
      reinstala o guard corrigido.
    - F6 (DESCARTADO por medição) — suspeita de que submit/review/abstain/legacy-ack/waive-verify também estivessem
      bloqueados: têm regra explícita em `guard.py:319-344`.
    
    ## Enforcement existente
    - Oráculo iter19 (CA-04 `cs-state show`) prova o show sem o hook; nenhum oráculo prova a lista do guard contra o
      argparse. Suíte harness tem o helper de hook pre-bash (`test_autonomy_install.py:104`), não usado para o show.

## [NOTA] 01-TASK-ORACULO — 2026-10-12T14:54:20-0300
- status: IN_PROGRESS · gate: PENDENTE

## [PASS] 01-TASK-ORACULO — 2026-10-12T14:59:42-0300
- status: DONE · gate: PASS
- oráculo congelado 524416ebaf44; base 3/9 nos 2 Pythons; calibrado
