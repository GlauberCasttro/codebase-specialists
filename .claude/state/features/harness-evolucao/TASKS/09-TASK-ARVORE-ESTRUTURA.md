# 09-TASK-ARVORE-ESTRUTURA — Avulsa só quando pequena; cardinalidade; dependências, critérios e datas em todo nível

id: 09-TASK-ARVORE-ESTRUTURA
feature: harness-evolucao
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-09, CA-10, CA-11
depends: 08-TASK-CLASSIFY-TEXTOS (edita o mesmo state.py e o mesmo teste), 07-TASK-SHELL-PORTAVEL (edita o mesmo tree.py)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
(1) `new task --avulsa` roda `quick_problems` (invariante escopada, área congelada, > 1 território → recusa "suba
para estruturado"); todo tipo exige ≥ 1 critério (CHORE com critério técnico); o histórico do item espelha tentativas
e vereditos da M2. (2) Cardinalidade: nenhum pai fecha sem filho; no fluxo de épico, sprint fecha só com ≥ 1 feature e
feature com ≥ 1 task; casos B e C preservados fora do épico. (3) `--depends-on` em `new task|feature|sprint` e no
`amend` antes do start, levado para a M2 no start, start recusa com dependência aberta, ciclo recusado;
`--aceite` em `new epico|sprint`, executado no close; `updated_at` e `status` persistidos em todo item; templates
`new-*.md` atualizados. NÃO mexer em close/reopen além da cardinalidade (é a 10).

## Contexto
CA-09, CA-10, CA-11. Âncoras: `scripts/harness/engine/tree.py:496-502` (avulsa sem quick_problems), `:433-436` e
`:687-689` (CHORE sem critério), `:989-996`/`:955-962`/`:931-950` (fecha sem filho), `:699` (depends_on vazio),
`:596-606` (amend só allowed_paths), `:377-396` (épico/sprint sem aceite), `:226-230` (sem updated_at),
`scripts/harness/engine/engine.py:893-926` (quick_problems); achados F10, F11, F13, F-R1 (lacuna menor).

## Subtasks
1. Rodar o oráculo (`-k CA09`, `-k CA10`, `-k CA11`) e ver falhar (RED).
2. Avulsa com quick_problems e critérios; cardinalidade no close e no `validate`.
3. Dependências na criação/amend e no start; aceite de épico/sprint; `updated_at`/`status`; templates `new-*.md`.
4. Testes em `scripts/harness/tests/test_evolucao_arvore.py`; oráculo, suíte `harness` e oráculo iter10 (casos A–D)
   nos 2 Pythons.

## Invariants
- Oráculo iter10 continua verde (casos B/C, task com dois pais recusada, ARCHIVE-1..6).
- Escrita de estado só pelo motor; cadeia de hash íntegra.

## Scope IN / OUT
IN: criação e estrutura dos itens. OUT: propagação/reabertura/furos de fechamento (10), nomes `.json` (11).

## Arquivos permitidos
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/tests/test_evolucao_arvore.py`
- `assets/templates/state/new-epic.md`
- `assets/templates/state/new-sprint.md`
- `assets/templates/state/new-feature.md`
- `assets/templates/state/new-task.md`

## AC
- Avulsa que toca invariante é recusada; épico/sprint/feature vazios não fecham; dependência aberta bloqueia o start;
  aceite vermelho do épico bloqueia o close; todo item tem `updated_at` e `status`.

## DoD
- Régua seletiva verde (harness) nos 2 Pythons; oráculo iter10 verde; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA10
python -m unittest discover -s campanhas/iter10/oraculo -p "test_*.py"
```

## Handoff
