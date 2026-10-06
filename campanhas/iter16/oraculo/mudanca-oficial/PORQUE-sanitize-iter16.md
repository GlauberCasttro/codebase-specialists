# Por que mudar `scripts/sanitize/tests/test_sanitize.py` (iter16, cobaia .NET)

Arquivo: `codebase-specialists/scripts/sanitize/tests/test_sanitize.py`, classe `ExamCopyRemovedAfterCheck`, `_exam`.

| versão | git blob | sha256 |
|---|---|---|
| antes = HEAD `18e3496` | `cf4d3b49d90b1c6041216ed9df91ba1e6a08c3c1` | `d260f60456fd73bdbe0d7dc068da853792d861b5e5036e04a87e71585d695eb8` |
| depois = viva (editada pela sessão cobaia .NET, não commitada) | `1f6a147d0a349395f0bd5a2068e42fb71fa0e968` | `9e35bf590a85cba28e5368918128ad1c7a7e75e41ea7a7a3f272d7631c271e77` |
| viva + `test_sanitize-iter16.patch` (proposta) | — | `d8a1bca09527530f2643a09c95ac72ed5c5a7b619c71aa7e1b9632108cbaaae3` |

## Por que a mudança é obrigatória
A mudança de produto U11 (`scripts/probes/exam.py`, `check`): com painel `why` pendente, o `probes check` **não**
apaga mais a cópia isolada do exame (`<out>/repo`), porque os juízes do painel leem o repo nela (cobaia .NET 2026-10-05:
a cópia apagada teve de ser recriada à mão). A versão do HEAD afirmava "cópia removida logo após o check", e o exame
do synth sempre tem `why` pendente. Medido: a versão do HEAD contra a skill viva dá **2 falhas em 8**
(`test_copy_inside_tmp_is_removed_after_check`, `test_copy_outside_target_is_removed_after_check`).

A versão viva ajusta o contrato: com painel pendente a cópia FICA; registra os vereditos (`panel why … --verdict PASS`),
roda o check de novo e então afirma a remoção. O que o teste prova continua (nenhuma cópia acumula), com o tempo certo.

## Por que o patch adicional (`test_sanitize-iter16.patch`)
Na viva, o caminho novo está dentro de `if pend:`. Se o banco do synth deixar de ter `why` para `dev-billing` (ou
`perfect` deixar de citar a fonte), o bloco é pulado **em silêncio** e o teste volta a passar sem exercer o contrato
novo. O patch troca o `if` por pré-condição explícita (`assertTrue(pend, …)`) e acrescenta que, depois do painel, o
check seguinte não tem nada pendente.

Aplicar (a partir de `~/.claude/skills/`):
`patch -p0 < campanhas/iter16/oraculo/mudanca-oficial/test_sanitize-iter16.patch`

Conferido:
- `patch -p0 --dry-run` sobre a viva: aplica limpo.
- Cópia da viva com o patch: `sanitize.tests.test_sanitize` **8/8 OK** em python3 3.13.3 e /usr/bin/python3 3.9.6.
- Cópia do HEAD (produto antigo) com o teste vivo + patch: 2 falhas, "cópia apagada com painel pendente" — o teste
  distingue o produto antigo do novo.
- O oráculo cobre o mesmo contrato por fora em `TestU11CopiaDoExameComPainelPendente` (com a pré-condição explícita).
