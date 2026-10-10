# 10-TASK-CICLO-VIDA — Propagação do fechamento, reabertura em cascata e nenhum fechamento sem validação

id: 10-TASK-CICLO-VIDA
feature: harness-evolucao
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-12, CA-13, CA-14
depends: 09-TASK-ARVORE-ESTRUTURA (edita o mesmo tree.py e o mesmo teste; usa o aceite de épico/sprint)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
(1) Propagação: no mesmo build do close de uma task, `_propagate` sobe pela árvore; o pai sem filho aberto e com
aceite verde fecha com evento `close {auto: true, gatilho}`; aceite vermelho deixa "pronto para fechar" no histórico
e o `next` mostra; o modo M5 deixa de engolir a recusa. (2) Reabertura em cascata: `reopen <task>` reabre os
ancestrais arquivados no mesmo evento (motivo + `cascata_de`), estaciona outra feature ativa com motivo, desarquiva só
os afetados. (3) Furos: close de task reaberta exige nova M2 ACCEPTED; `--devolver` roda o aceite; item do backlog
nunca iniciado não fecha (aponta `drop`); `feature drop` marca tasks como descartadas; `status_of` mostra reaberta;
`close-task.md` não promete `--devolver` em task. Templates `close-*.md` e `reopen.md` explicam a propagação;
docs/10 atualizado. NÃO tirar o close humano explícito (continua disponível); NÃO mudar nomes de arquivo (11).

## Contexto
CA-12, CA-13, CA-14. Âncoras: `scripts/harness/engine/tree.py:922-923` (sem propagação), `:1052-1055` (recusa com
pai fechado), `:1042-1063` (reopen sem checar feature ativa), `:896-899` (close da reaberta), `:947` (devolver pula
aceite), `:885-889` (backlog fecha), `:1033-1034` (drop como fechada), `:1182-1193` (status), `scripts/harness/engine/
session.py:335,364-367` (next), `scripts/harness/engine/auto.py:1177-1183` (M5 engole recusa),
`assets/templates/state/close-task.md:11`; achados F15–F23.

## Subtasks
1. Rodar o oráculo (`-k CA12`, `-k CA13`, `-k CA14`) e ver falhar (RED).
2. `_propagate` no close e "pronto para fechar" no `next`; M5 sem engolir recusa.
3. Cascata no reopen com park da feature ativa; furos de validação; status de reaberta.
4. Templates e docs/10; testes em `scripts/harness/tests/test_evolucao_arvore.py`; oráculo, suíte `harness`,
   oráculos iter10 e m5 nos 2 Pythons.

## Invariants
- "Uma feature ativa por vez" e "nada fechado dentro de state/" continuam valendo (validate OK após cada operação).
- Todo fechamento automático é evento encadeado com o gatilho.

## Scope IN / OUT
IN: close, reopen, drop, status, next, propagação. OUT: classificação (08), estrutura (09), JSON (11), relatório (12).

## Arquivos permitidos
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/tests/test_evolucao_arvore.py`
- `assets/templates/state/close-task.md`
- `assets/templates/state/close-feature.md`
- `assets/templates/state/close-sprint.md`
- `assets/templates/state/close-epic.md`
- `assets/templates/state/reopen.md`
- `docs/10-arvore-de-estado.md`

## AC
- Fechar a última task fecha feature, sprint e épico com aceites verdes; reabrir a task arquivada reabre os três;
  reaberta e `--devolver` com aceite vermelho não fecham.

## DoD
- Régua seletiva verde (harness) nos 2 Pythons; oráculos iter10 e m5 verdes; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA12
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA13
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA14
```

## Handoff
