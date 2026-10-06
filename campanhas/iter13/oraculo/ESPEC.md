# ESPEC — oráculo campanha-iter13 (pendências menores)

Oráculo: `test_menores.py` (20 testes, unittest puro, Python 3.9+, alvos em `tempfile`). Base: `base.txt`
(skill atual, 3.13 e 3.9: **18 falham, 2 passam**, e os 2 que passam são regressão). Quem implementa **não edita**
o oráculo. Mudança num teste congelado da skill: `mudanca-oficial/` (patch + PORQUE.md).

Como o oráculo observa: emissor real `emit.cli.main` em processo (igual a `scripts/emit/tests`, com o team
sintético de `scripts/emit/tests/fixture.py`), motor real `engine/state.py` em subprocesso, `cs.py` em
subprocesso, wrapper `.swarm/bin/cs-state` do alvo instalado. Skill: `$CS_SKILL_DIR`, senão
`~/.claude/skills/codebase-specialists`. Rodar: `python3 -m unittest -v test_menores` (de dentro desta pasta).

## 1. Requisito → testes

| Req | O que se prova | Testes |
|---|---|---|
| R1 emit multiplataforma | As 23 skills (14 `STATE_SKILLS` + 9 `AUTO_SKILLS`) saem para Cursor, Copilot e Codex nos caminhos do §2.1; `name` = diretório, `description` não vazia, marcador de gerado; o corpo cita o comando real `.swarm/bin/cs-state <sub>`/`.swarm/bin/cs-auto <sub>` | `TestR1EmitSkillsMultiplataforma.test_cursor_…`, `test_copilot_…`, `test_codex_…` |
| R1 política de invocação | Cursor/Copilot: skill humana tem `disable-model-invocation: true` e as de consulta/criação não têm. Codex (sem o campo): o corpo da humana diz "só o humano executa" e o da invocável **não** diz | idem (negativos incluídos) |
| R1 guard continua bloqueando | Todo `.swarm/bin/cs-auto approve/amend/resolve/stop/abort …` citado nas skills não-Claude é reconhecido pelo guard como ato HUMANO (`auto.human_act_in_command`, usado por `guard.decide_bash`) | `test_guard_continua_bloqueando_os_comandos_humanos_citados` |
| R1 regressão Claude | `.claude/skills/<n>/SKILL.md` continua igual (política e comando) | `test_claude_code_continua_igual` (passa hoje) |
| R1 independência | `--platforms cursor` (ou copilot, ou codex) sozinho gera as 23, não escreve `.claude/skills/`, e o `validate` dessa plataforma passa; `--dry-run` lista as novas saídas no bloco `outside` | `TestR1CadaPlataformaSozinha.*` |
| R1 `emit validate` cobre | Verde logo após o emit. Falha **nomeando o caminho** quando: a skill está ausente; a política foi tirada à mão (linha `disable-model-invocation` removida / frase "só o humano executa" trocada); há um órfão com marcador de gerado em `<dir de skills da plataforma>/skill-que-saiu/SKILL.md` | `TestR1ValidateCobre.*` |
| R2 reroute | Task da árvore ESCALATED → `reroute --agent dev-billing-sr --decision …`: o arquivo da task traz `agent` novo; `cs-state board` mostra o novo agente; evento novo com `data.de.agent`=antigo e `data.para.agent`=novo; `validate` verde. Depois do `ready` da nova delegação, o `route` do arquivo = `{model, band}` da delegação vigente | `TestR2RerouteRetryNaArvore.test_reroute_…` |
| R2 retry | REJECTED → `retry --findings`: o roteador sobe o tier (sonnet→opus, precondição verificada); o arquivo traz o `route` novo; evento com `data.de.route`=antigo e `data.para.route`=novo; `validate` verde | `test_retry_atualiza_route_…` |
| R2 retomada humana | ESCALATED → `retry --decision`: arquivo coerente com a delegação (`route`, `agent`) e evento com `de`/`para` | `test_retry_por_decisao_humana_…` |
| R3 init em árvore | Depois de `cs.py init --platforms claude-code` + `cs.py harness install --allow-outside --git-hook`: existem `SD/backlog`, `SD/state`, `SD/archive` e `SD/events.jsonl`; nenhum `board.json5` em lugar nenhum de `SD/` (nem em backup) | `TestR3InitNasceEmArvore.test_zonas_…` |
| R3 sem migração | 1º evento da cadeia: `type: "init"`, `data.layout: "tree"`; nenhum evento com "migra" no tipo | `test_nasce_em_arvore_sem_migracao` |
| R3 utilizável | `cs-state tree`, `tree --json` (JSON válido) e `board` saem 0 sem `migrate`; `new epico` cria em `SD/backlog/`; `validate` 0 | `test_cs_state_tree_…`, `test_arvore_utilizavel_…` |
| R3 idempotência | Reinstalar (mesmo caminho) não cria board plano, não migra, e `tree` segue 0 | `test_reinstalar_mantem_arvore` |
| R3 regressão | `cs.py harness selftest` 0 | `test_selftest_verde` (passa hoje) |

## 2. Interfaces FIXADAS

### 2.1 Caminhos de saída por plataforma (`<n>` = nome da skill, ex. `close-task`)
| Plataforma | Caminho | Frontmatter mínimo | Política humana |
|---|---|---|---|
| Claude Code | `.claude/skills/<n>/SKILL.md` (já existe) | `name`, `description`, … | `disable-model-invocation: true` |
| Cursor | `.cursor/skills/<n>/SKILL.md` | `name` (= `<n>`), `description` | `disable-model-invocation: true` |
| GitHub Copilot | `.github/skills/<n>/SKILL.md` | `name` (= `<n>`), `description` | `disable-model-invocation: true` |
| Codex | `.agents/skills/<n>/SKILL.md` | `name` (= `<n>`), `description` | corpo contém **"só o humano executa"** (case-insensitive) |

Todos são arquivos inteiros gerados (modo OWNED, com `codebase-specialists:generated`), frontmatter YAML legível
por `emit.common.parse_frontmatter`. As 23 skills, o flag humano e o subcomando que o corpo tem de citar estão
na tupla `SKILLS` do oráculo (é uma cópia congelada de `STATE_SKILLS`/`AUTO_SKILLS`; o oráculo não importa a tabela
do código).

Fonte dos formatos (o implementador confere na doc oficial e registra em `references/platforms.md` §1/§2/§4.1 +
`emit/validate.py`, conforme manda o próprio platforms.md):
- Cursor Agent Skills: `.cursor/skills/<n>/SKILL.md`, campos `name`, `description`, `disable-model-invocation`
  (cursor.com/docs/context/skills).
- VS Code / Copilot Agent Skills: `.github/skills/<n>/SKILL.md`, campos `name`, `description`, `argument-hint`,
  `user-invokable`, `disable-model-invocation` (code.visualstudio.com/docs/copilot/customization/agent-skills).
- Codex skills: repositório em `.agents/skills/<n>/SKILL.md`, campos `name`, `description`. **Não existe**
  `disable-model-invocation`. O equivalente nativo, se a doc confirmar, é `agents/openai.yaml` com
  `policy.allow_implicit_invocation: false`. O oráculo **não exige** esse arquivo (é opcional); exige o texto.
- **Se a doc oficial divergir** de algum caminho acima, o implementador **para e devolve ao repositório-piloto** (não adapta o
  oráculo por conta própria). Só o repositório-piloto ajusta a constante `OUT` antes do congelamento.

### 2.2 Validate (G7)
`cs.py emit validate --platforms …` sai ≠0 e cita o caminho do arquivo quando: falta a saída, a saída difere do
que o emit geraria (frescor), a política humana foi removida, ou há um órfão com marcador de gerado nos diretórios
`.cursor/skills/`, `.github/skills/` e `.agents/skills/` (poda: prefixos da plataforma em `_orphans`/`GEN_DIRS`).
O `--dry-run` lista as novas escritas no bloco `outside`, porque elas ficam fora de `.swarm/`.

### 2.3 Evento de reroute/retry (R2)
Pelo menos um evento **apendado pelo próprio comando** cita a task (id da árvore ou da M2 no JSON do evento) e tem
`data.de` e `data.para` como **objetos**:
- `reroute`: `de.agent` = agente antigo, `para.agent` = agente novo (`route` pode vir junto, nulo até o `ready`);
- `retry` (de REJECTED ou retomada de ESCALATED): `de.route` e `para.route` = `{model, band}` antes e depois.

Segue a convenção `de`/`para` que os eventos `arvore.move` já usam. O arquivo da task (`agent`, `route: {model,
band}`) é materializado pelo motor (escritor único). Comparação de route só por `model` e `band`.

### 2.4 Init (R3)
"Alvo novo" = o caminho SWARM-DIR-1 (`cs.py init --platforms claude-code` e depois `cs.py harness install
--allow-outside --git-hook`), o mesmo de `scripts/harness/tests/test_swarm_dir.py::fresh_install`. O estado nasce
pelo `init` de árvore (1º evento `init`/`layout: tree`), não por board plano seguido de `migrate`.

## 3. Decisões do escritor do oráculo (para o repositório-piloto conferir)
1. **Caminhos multiplataforma** (§2.1): o emit atual não tem formato de skill para Cursor, Copilot nem Codex (lá os
   comandos são "linhas de terminal no S0", platforms.md §2). Escolhi o formato nativo de Agent Skills de cada
   plataforma porque é o único em que a política de invocação existe. Se o repositório-piloto preferir outro, troca `OUT` e
   esta tabela antes de congelar.
2. **Codex**: o texto "só o humano executa" vai só nas 9 skills humanas e é proibido nas 14 invocáveis. Para
   Cursor/Copilot o oráculo exige o campo e não exige o texto.
3. **R3 "cs.py init"**: hoje `cs.py init` sozinho só cria `run.json5`; quem cria o estado é `harness install`
   (`engine.init_state`). O oráculo observa o caminho completo (o mesmo do teste congelado), sem impor em qual dos
   dois comandos a árvore nasce.
4. **R2 route no reroute**: a nova delegação nasce PLANNED, sem rota; por isso a igualdade do `route` é checada
   depois do `ready` (que é quando o roteador decide).
5. Os testes que passam hoje (`test_claude_code_continua_igual`, `test_selftest_verde`) são regressão de propósito.
