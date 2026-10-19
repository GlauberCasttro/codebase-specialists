# 05-TASK-TEXTOS-EN — Textos do produto citando só flags en; cs-auto no doctest

id: 05-TASK-TEXTOS-EN
feature: iter27
tipo: CORRECAO
grupo: G3
agente: corretor (papel; executor e model no Handoff)
CA: CA-05, CA-06
depends: 02-TASK-FLAGS-EN (os nomes en do cs-state/cs-auto/cs-route têm de existir para o doctest parsear), 04-TASK-INCLUDE-EMITTED (idem para --include-emitted)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
Trocar toda citação de flag pt nos textos do produto (skills e templates emitidos, SKILL.md, MODO-DE-USO.md,
references, docs, `scripts/emit/platforms.py`) pelo nome en; pôr o cs-auto entre os bins do doctest de comandos.
NÃO traduzir a prosa (D-07), NÃO mexer na entrada histórica de `references/migrations.json5` nem em
`docs/09-upgrade.md` (task 06), NÃO mudar código do motor, NÃO enfraquecer o doctest (só acrescentar o bin).

## Contexto
CA-05 (textos) e CA-06. Âncoras: U2 da E2 (311 citações), `assets/templates/state/auto-plan.md:4,6`,
`assets/templates/state/new-task.md:5,7,10`, `scripts/doctests/tests/test_commands_parse.py:78-83` (F8),
`scripts/emit/platforms.py` (1 citação de `--avulsa`), `docs/06-referencia-cli.md` (34; regerar o help como na
iter26). Os nomes en são os da FEATURE.md (CA-01, CA-02, CA-04).

## Subtasks
1. Rodar TestCA05/06 e ver vermelho.
2. Substituir as citações nos templates emitidos e em platforms.py; conferir com o doctest.
3. Substituir em SKILL.md, MODO-DE-USO.md, references e docs; regerar a referência da CLI.
4. cs-auto em `BINS` do doctest; teste novo `test_iter27_textos.py` (varre os textos emitidos e executa os exemplos
   com `--dry-run`).

## Invariants
- Prosa em português; nenhum comando citado deixa de parsear.
- O oráculo da iter26 (textos sem flag pt) segue verde.

## Scope IN / OUT
IN: textos e o doctest. OUT: código do motor e dos CLIs (02, 04), VERSION/migrations/docs/09 (06).

## Arquivos permitidos
- `assets/templates/feature-autonoma.md`
- `assets/templates/plan-sprint.md`
- `assets/templates/product-process.md`
- `assets/templates/state/auto-amend.md`
- `assets/templates/state/auto-approve.md`
- `assets/templates/state/auto-plan.md`
- `assets/templates/state/auto-resolve.md`
- `assets/templates/state/close-task.md`
- `assets/templates/state/move.md`
- `assets/templates/state/new-epic.md`
- `assets/templates/state/new-feature.md`
- `assets/templates/state/new-sprint.md`
- `assets/templates/state/new-story.md`
- `assets/templates/state/new-task.md`
- `scripts/emit/platforms.py`
- `SKILL.md`
- `MODO-DE-USO.md`
- `references/harness.md`
- `references/platforms.md`
- `references/stages.json5`
- `references/ARCHITECTURE.md`
- `docs/02-harness.md`
- `docs/04-roteador-de-modelos.md`
- `docs/06-referencia-cli.md`
- `docs/10-arvore-de-estado.md`
- `docs/11-modo-autonomo.md`
- `docs/PONTOS-DO-FOUNDER.md`
- `docs/README.md`
- `docs/ROADMAP-proxima-rodada.md`
- `docs/ROADMAP-rodada-seguinte.md`
- `docs/exemplos/walkthrough-py-billing.md`
- `docs/fases/05-validate.md`
- `scripts/doctests/tests/test_commands_parse.py`
- `scripts/emit/tests/test_iter27_textos.py`

## AC
- TestCA05 (exceto a parte do upgrade, que é da 06) e TestCA06 verdes nos 2 Pythons; suítes doctests e emit verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff com a contagem "citações pt: 311 → 0".

## Verificação
```bash
cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA05 test_iter27.TestCA06 && cd ../../.. && python3 .claude/tools/e2e.py rodar --suites doctests,emit
```

## Handoff
