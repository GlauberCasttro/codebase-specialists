# 06-TASK-CORRECT-ESCOPO — correct com escopo, registro do §11.4, reexecução, log de consulta e lição de falha com causa

id: 06-TASK-CORRECT-ESCOPO
feature: harness-evolucao
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-04, CA-06, CA-17
depends: 05-TASK-MEMORIA-INIT (edita o mesmo mem.py, guard.py e teste; usa o layout criado)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
(1) `cs-mem correct --scope agent|project|execution --task <id>` (execution exige `--task`; project grava na memória
do projeto como rule/decision com source correct; execution grava só no histórico da task, nunca no índice global);
registro com os campos do §11.4 (originalRequest copiado da task, incorrectBehavior, correction, expectedBehavior,
confidence, applicationCount, source "correct"), evento `lesson.recorded` pelo ledger do motor; (2) `correct.md` pede
o escopo, passa o texto do usuário sanitizado e manda reexecutar a task (`cs-state retry`/`reopen`) e validar;
(3) o hook SubagentStart grava `memory_injected {task, agent, lesson_ids, hit_ids, omitted}` e a seção MEMÓRIA do
brief ganha prioridade reservada; API `mem.mark_applied(ids)` que incrementa `applicationCount`; (4) a lição
automática de falha só nasce no ACCEPTED pós-falha, com causa e correção vindas do retry estruturado, e falha de
ambiente não vira lição. NÃO exigir `lessons_checked` na submissão aqui (é a 12, em engine.py).

## Contexto
CA-04, CA-06 (log e contagem), CA-17 (lição com causa). Âncoras: `scripts/memory/mem.py:1161-1168` (CLI sem
scope/task), `:956` (rule fundida), `:780` (LESSON_SOURCES sem correct), `:888` (sem evento), `:979-999`
(capture_from_event grava sintoma), `assets/templates/correct.md:1-5`, `scripts/harness/engine/brief.py:139-160`
(prioridade 6, sem log), `scripts/harness/engine/guard.py:399-423` (SubagentStart); achados F6, F7, F33.

## Subtasks
1. Rodar o oráculo (`-k CA04`, `-k CA06`, `-k CA17`) e ver falhar (RED).
2. Escopo e registro no `mem.py`/`cli.py`; evento pelo ledger; template `correct.md` e `memory.md`; docs/03.
3. Log de injeção no SubagentStart (guard.py) e prioridade da MEMÓRIA no brief; `mark_applied`.
4. Lição de falha com causa no ACCEPTED pós-falha; testes em `scripts/memory/tests/test_evolucao_memoria.py`;
   oráculo e suítes de `memory` e `harness` nos 2 Pythons.

## Invariants
- Correção de escopo execution nunca aparece em inject/search de outra task.
- Nenhum segredo no registro (a redação da 04 vale para todos os campos novos).

## Scope IN / OUT
IN: correct, registro, log de consulta, lição de falha. OUT: submissão (12), relatório (12), init (05).

## Arquivos permitidos
- `scripts/memory/mem.py`
- `scripts/memory/cli.py`
- `scripts/memory/tests/test_evolucao_memoria.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/brief.py`
- `assets/templates/correct.md`
- `assets/templates/memory.md`
- `docs/03-memoria-e-licoes.md`

## AC
- Os 3 escopos gravam no lugar certo com o registro completo e o evento; o SubagentStart deixa `memory_injected` no
  ledger; a lição de falha guarda causa e correção.

## DoD
- Régua seletiva verde (memory, harness) nos 2 Pythons; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA04
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA06
```

## Handoff
