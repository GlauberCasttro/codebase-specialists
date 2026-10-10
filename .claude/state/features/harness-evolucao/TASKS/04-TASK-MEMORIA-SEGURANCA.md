# 04-TASK-MEMORIA-SEGURANCA — Segredo redigido, isolamento entre agentes, conflito e promoção, check portátil

id: 04-TASK-MEMORIA-SEGURANCA
feature: harness-evolucao
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-01, CA-02, CA-05, CA-15
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: IN_PROGRESS
gate: FAIL
complexidade: normal

## Goal
(1) `redact()` autocontido em `mem.py`, aplicado em `add_lesson`/`make_entry` antes de gravar e antes de indexar, com
`[REDACTED:<tipo>]` e contagem na saída; (2) guard recusa `--agent` repetido (inclusive `--agent=`) e o `mem.py`
recusa `--agent` repetido e agente fora do `team.json5` (+ `lead`); (3) correção com wrong/right invertidos cria lição
nova com `supersedes`, a antiga vira `superseded` com histórico, sem promover; lição `promoted` não aplicada continua
em inject/search; (4) `cs-mem check` executa a lição com shell portátil (sem `/bin/sh` fixo). NÃO mudar o formato de
arquivo (é a 05), NÃO mexer no escopo do correct (é a 06).

## Contexto
CA-01, CA-02, CA-05, CA-15 (parte do `mem.check`). Âncoras: `scripts/memory/mem.py:955` (sem redação), `:910`
(Jaccard trata contradição como recorrência), `:858` e `:1056`/`:504-505` (promovida some), `:784` (agente só por
regex), `:1027` (`/bin/sh`); `scripts/harness/engine/guard.py:193-199,261` (só o 1º `--agent`); achados F1, F2, F4,
F5, F8c, F30.

## Subtasks
1. Rodar o oráculo (`-k CA01`, `-k CA02`, `-k CA05`, `-k CA15`) e ver falhar (RED).
2. Redação, validação de agente e recusa de `--agent` repetido (guard + mem); testes em
   `scripts/memory/tests/test_evolucao_memoria.py`.
3. Detecção de contradição (pares wrong/right invertidos) com `supersedes`/`superseded`; promovida injetável até
   `applied`; shell portátil no check.
4. Rodar o oráculo e as suítes de `memory` e `harness` nos 2 Pythons.

## Invariants
- O agente principal continua podendo gravar na memória de qualquer agente (é o dono do `/correct`).
- Nenhum `def` some; teto de 30 lições e decaimento preservados para lições comuns.

## Scope IN / OUT
IN: memória do agente, guard do cs-mem. OUT: init (05), escopo/registro/log (06), formato de arquivo (05).

## Arquivos permitidos
- `scripts/memory/mem.py`
- `scripts/memory/cli.py`
- `scripts/memory/tests/test_evolucao_memoria.py`
- `scripts/harness/engine/guard.py`

## AC
- Token fictício nunca aparece em arquivo de memória, índice ou inject; `--agent eu --agent outro` recusado no guard e
  no cs-mem; contradição substitui; promovida aparece no inject.

## DoD
- Régua seletiva verde (memory, harness) nos 2 Pythons; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA01
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA02
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA05
```

## Handoff
