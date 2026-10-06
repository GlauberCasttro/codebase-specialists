# Mudança oficial — `scripts/sanitize/tests/test_sanitize.py` (campanha-iter11)

- Arquivo: `codebase-specialists/scripts/sanitize/tests/test_sanitize.py`
- sha256 ANTES: `91ec236e611152d4990cc78093ba29e50c5beb29afc4305a60902827361bc652`
- sha256 DEPOIS (com o patch): `d260f60456fd73bdbe0d7dc068da853792d861b5e5036e04a87e71585d695eb8`
- Patch: `test_sanitize.patch` (sha256 `014f388fff9c57a8391dff96ae86b5b12bd40fea4d856b101719c26e5472d6e8`),
  aplicar com `cd ~/.claude/skills && patch -p0 < .../mudanca-oficial/test_sanitize.patch`.

## Conflito

A iter11 (ESPEC §13, P-1) torna ÚNICO o caminho das respostas do exame guiado: o examinado grava no
`answer_file` de `questions.json5` (`<alvo>/.swarm/probes/exams/<agente>.answers.json5`) e a pontuação é
`cs.py probes check <agente>` sem `--answers`. `--answers <outro caminho>` no modo guiado sai com exit 2
("não é o caminho único das respostas"); antes era copiado em silêncio para o canônico (o 2º/3º caminho que a
iter11 elimina).

O helper `ExamCopyRemovedAfterCheck._exam` usava justamente esse caminho extra: gravava em `<out>/answers.json5` e
chamava `probes check AGENT --answers <out>/answers.json5`. Com o produto da iter11 isso dá exit 2 e quebra
`test_copy_inside_tmp_is_removed_after_check` e `test_copy_outside_target_is_removed_after_check` antes de chegar
ao que eles protegem (a remoção da cópia de exame).

## O que muda (só `_exam`)

1. Lê `answer_file` do `questions.json5` gerado pelo `exam-pack --out` (o caminho que o examinado de verdade recebe).
2. NOVA asserção: esse `answer_file` é o canônico `<alvo>/.swarm/probes/exams/<agente>.answers.json5`.
3. Grava as respostas perfeitas nele e chama `probes check AGENT` sem `--answers`.

Nada mais muda: setUp, os dois testes, `test_foreign_dir_is_never_removed` e as demais classes ficam idênticos.

## Por que nenhuma asserção ficou mais fraca

| Asserção | Antes | Depois |
|---|---|---|
| exam-pack exit 0 e `<out>/repo/.git` existe | sim | idem |
| `probes check` com código em (0, 1) e saída com `dev-billing:` | sim | idem (agora pelo caminho único) |
| `exams/<agente>.answers.json5` existe | sim | idem* |
| `reports/<agente>.json5` gravado | sim | idem — prova que o check pontuou |
| cópia `<out>/repo` removida (dentro de `.swarm/tmp` e fora do alvo) | sim | idem |
| ponteiro `<agente>.exam-copy.json5` removido | sim | idem |
| alvo intacto (`src/billing/invoice.py`) | sim | idem |
| refino: novo exam-pack no mesmo `--out` funciona | sim | idem |
| `answer_file` do pacote = caminho canônico | — | NOVA |

\* Antes, a existência do canônico provava a cópia silenciosa `--answers → canônico`; essa cópia é exatamente o
comportamento que a iter11 proíbe (e `test_iter3_refine.py:202-208` já exige a recusa sem cópia). A garantia
equivalente agora é a nova asserção (o pacote aponta para o canônico) + o relatório gravado em `reports/`, que só
existe se o check leu as respostas desse caminho.

## Verificação (na cópia `scratchpad/iter11-sanitize/copia/`)

- `patch -p0` limpo; `cd scripts/sanitize && PYTHONDONTWRITEBYTECODE=1 CS_SKILL_DIR=<cópia> <py> -m unittest discover -s tests`:
  python3 3.13.3 → Ran 8, OK; /usr/bin/python3 3.9.6 → Ran 8, OK.
- Sem patch (skill atual): 8 testes, FAILED (failures=2) — os dois acima.
- Mutação: `remove_exam_copy` com `return None` no início (remoção no-op) → nos 2 Pythons FAILED (failures=2):
  `test_copy_inside_tmp_is_removed_after_check` ("cópia de exame acumulada após o check") e
  `test_copy_outside_target_is_removed_after_check`. Desfeita a mutação → 8/8 OK.
