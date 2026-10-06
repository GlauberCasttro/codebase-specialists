# Por que mexer em dois oráculos congelados (iter10 e iter13)

Os patches se aplicam a partir de `~/.claude/skills/`, com `patch -p0 < campanhas/iter15/oraculo/mudanca-oficial/<arquivo>.patch`.
Os dois foram conferidos com `patch -p0 --dry-run`.

| Patch | Arquivo | sha256 antes |
|---|---|---|
| `iter10-test_estado_arvore.patch` | `campanhas/iter10/oraculo/test_estado_arvore.py` | `4c544d4c6d226377c549b63db27c5e9687935b45072cf6fc6c86f9fc4d5fdf6f` |
| `iter13-test_menores.patch` | `campanhas/iter13/oraculo/test_menores.py` | `c928181561a2d4d6cb21f55526e29bde032857f7c7ed833f69fba006c817a641` |

## O conflito
O R1 da iter15 (decisão do founder) renomeia `new-epico` para `new-epic` e `close-epico` para `close-epic` em todas as
plataformas. Os dois oráculos anteriores congelam os nomes antigos como **nome de pasta de skill**:
- iter10, `TestSkillsEmitidas`: `SKILLS_CLI`, `CRIACAO`, `MUDANCA` e `DOR_FLAGS`. Os testes procuram
  `.claude/skills/new-epico/SKILL.md`.
- iter13: a tupla `SKILLS`. Os testes procuram `<dir>/new-epico/SKILL.md` em Cursor, Copilot e Codex.

Sem o patch, implementar o R1 deixa vermelhos 5 testes de cada oráculo. Mantê-los verdes impede o R1.

## O que muda (só isso)
Só a **chave/nome** da skill: `"new-epico"` passa a `"new-epic"` e `"close-epico"` passa a `"close-epic"`. Os subcomandos
do motor que esses testes exigem no corpo (`cs-state new epico`, `cs-state close`), as flags de DoR (`--objetivo`) e as
políticas (só humano ou invocável) **não mudam**.

## Por que não enfraquece nada
- O que esses oráculos provam continua o mesmo, com o nome novo: skill fina, corpo que cita o comando real, política
  de invocação, DoR, emissão multiplataforma e `validate` que acusa ausência ou edição.
- Prova executada: com a implementação de referência da iter15 (`…/scratchpad/iter15-mut/ref`), cada oráculo
  **original** dá 5 falhas e o **com patch** dá OK. Foram 8/8 em `TestSkillsEmitidas` e 11/11 nas classes R1 da iter13.
  Com a skill viva de hoje, o oráculo com patch falha 5 vezes. Ou seja, o patch troca a exigência pelo nome novo e não
  a remove.
- A suíte da própria skill (`scripts/*/tests`) **não** precisa de patch. Nenhum teste dela exige os nomes antigos, e
  ela deu o mesmo resultado na cópia viva e na referência.
