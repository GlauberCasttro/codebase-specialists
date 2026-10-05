# Plataformas — formatos confirmados e mapeamento da emissão

Normativo para `scripts/emit/`. Formatos verificados na documentação oficial em **2026-10-01**
(data de acesso; Agent Skills de Cursor/Copilot/Codex conferidas em **2026-10-05**). Quando a doc mudar, atualize esta tabela **e** o validador (`scripts/emit/validate.py`),
que é o gate G7. Fonte de verdade da emissão: `.swarm/team.json5` + `.swarm/facts/*.json5`.

## 1. Formatos confirmados (com fonte)

| Plataforma | Artefato | Formato confirmado | Fonte (acesso 2026-10-01) |
|---|---|---|---|
| Claude Code | subagente `.claude/agents/<n>.md` | frontmatter YAML; obrigatórios `name` (sem `:`), `description`; opcionais `tools` (string com vírgulas ou lista), `disallowedTools`, `model` (`sonnet`/`opus`/`haiku`/`fable`/id `claude-*`/`inherit`), `permissionMode`, `maxTurns`, `skills` (pré-carrega o conteúdo inteiro), `mcpServers`, `hooks`, `memory` (`user`/`project`/`local`), `background`, `omitClaudeMd`, `effort`, `isolation`, `color`, `initialPrompt`, `experimental` | https://code.claude.com/docs/en/sub-agents |
| Claude Code | memória por agente | `memory: project` → `.claude/agent-memory/<n>/`, `MEMORY.md` (200 linhas/25 KB) entra no prompt; Read/Write/Edit são habilitados para o diretório de memória, **mas `disallowedTools` explícito prevalece** | idem, seção "Enable persistent memory" |
| Claude Code | `CLAUDE.md` | raiz ou `.claude/CLAUDE.md`; alvo <200 linhas; comentários HTML de bloco são removidos antes de entrar no contexto; `@path` importa (carrega no início) | https://code.claude.com/docs/en/memory |
| Claude Code | regras `.claude/rules/*.md` | frontmatter só com `paths:` (lista YAML ou string com vírgulas); sem `paths` = sempre carregada; com `paths` carrega quando um arquivo casado é lido | idem, "Path-specific rules" |
| Claude Code | skill/comando `.claude/skills/<n>/SKILL.md` | cria `/<n>`; `.claude/commands/` virou skill; campos `name`, `description` (≤1.536 car. com `when_to_use`), `disable-model-invocation`, `allowed-tools`, `argument-hint`, `arguments`, `paths`…; `` !`cmd` `` roda antes e injeta a saída; `$ARGUMENTS`/`$0` | https://code.claude.com/docs/en/skills |
| Claude Code | `AGENTS.md` | lido só quando não há `CLAUDE.md` (padrão `claude-md-or-agents-md`) | https://code.claude.com/docs/en/memory#agents-md |
| Cursor | regras `.cursor/rules/*.mdc` | frontmatter `description`, `globs` (**string, padrões separados por vírgula**, sem aspas nos exemplos oficiais), `alwaysApply` (bool); `alwaysApply: true` ignora globs | https://cursor.com/docs/context/rules |
| Cursor | subagentes `.cursor/agents/*.md` | frontmatter `name`, `description`, `model` (`inherit` padrão), `readonly` (bool), `is_background` (bool). **O Cursor também lê `.claude/agents/` e `.codex/agents/`** | https://cursor.com/docs/context/subagents |
| Cursor | skills `.cursor/skills/<n>/SKILL.md` | frontmatter `name` (= diretório), `description`; opcionais `disable-model-invocation`, `license`, `compatibility`, `metadata` (acesso 2026-10-05) | https://cursor.com/docs/context/skills |
| Copilot | skills `.github/skills/<n>/SKILL.md` | frontmatter `name` (= diretório), `description`; opcionais `argument-hint`, `user-invokable`, `disable-model-invocation`, `license`, `compatibility`, `metadata` (acesso 2026-10-05) | https://learn.microsoft.com/en-us/visualstudio/ide/copilot-agent-skills |
| Codex | skills `.agents/skills/<n>/SKILL.md` | frontmatter `name`, `description`; opcionais `license`, `compatibility`, `metadata`. **Não existe `disable-model-invocation`** (acesso 2026-10-05) | https://github.com/vercel-labs/skills (`.agents/skills`) |
| Cursor | `AGENTS.md` | raiz e aninhado; o mais específico prevalece | https://cursor.com/docs/context/rules |
| Copilot | `.github/copilot-instructions.md` | Markdown livre, vale para o repositório inteiro | https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions |
| Copilot | `.github/instructions/<n>.instructions.md` | frontmatter `applyTo` (glob; vários separados por vírgula), `excludeAgent` opcional | idem |
| Copilot | agentes `.github/agents/<n>.agent.md` | `description` obrigatório; `name`, `target`, `tools` (aliases `read`, `edit`, `search`, `execute`, `agent`, `web`…; `[]` = nenhuma), `model`, `disable-model-invocation`, `user-invocable`, `mcp-servers`, `metadata`; corpo ≤30.000 caracteres | https://docs.github.com/en/copilot/reference/custom-agents-configuration · https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents |
| Copilot | `AGENTS.md` | vários no repo; o mais próximo na árvore prevalece | add-repository-instructions (acima) |
| Codex | `AGENTS.md` | concatena da raiz do git até o cwd (o mais próximo aparece por último e prevalece); `AGENTS.override.md`; limite `project_doc_max_bytes` = 32 KiB | https://learn.chatgpt.com/docs/agent-configuration/agents-md |
| Codex | agentes `.codex/agents/<n>.toml` | obrigatórios `name`, `description`, `developer_instructions`; opcionais `model`, `model_reasoning_effort`, `sandbox_mode` (`read-only`/`workspace-write`), `mcp_servers`, `skills.config` | https://learn.chatgpt.com/docs/agent-configuration/subagents |

## 2. O que é emitido, por camada de steering (§8-ter)

Markdown só onde a plataforma exige (§8-decies); o que é da skill sai em JSON5.

| Camada (orçamento) | Claude Code | Cursor | Copilot | Codex |
|---|---|---|---|---|
| S0 núcleo (≤40 linhas) | bloco gerenciado em `CLAUDE.md` | `.cursor/rules/cs-core.mdc` (`alwaysApply: true`) | bloco em `.github/copilot-instructions.md` | bloco em `AGENTS.md` raiz |
| Kernel do orquestrador (≤80) | `.claude/orchestrator.md` (S0 aponta; injeção pelo hook `SessionStart` do harness) | `.cursor/rules/cs-orchestrator.mdc` (`alwaysApply: true`) | mesmo bloco do S0, após o núcleo | mesmo bloco do S0, após o núcleo |
| S1 cartão (≤80) | `.claude/agents/<n>.md` | `.cursor/agents/<n>.md` | `.github/agents/<n>.agent.md` | `.codex/agents/<n>.toml` (`developer_instructions`) |
| S2 território (≤60) | `.claude/rules/cs-<n>.md` (`paths:`) | `.cursor/rules/cs-<n>.mdc` (`globs`) | `.github/instructions/cs-<n>.instructions.md` (`applyTo`) | `<dir>/AGENTS.md` aninhado quando o território é `dir/**`; senão `.swarm/territories/<n>.json5` |
| S4 playbooks | `.claude/skills/<n>-playbooks/SKILL.md` (não listado em `skills:` para não pré-carregar) | `.swarm/playbooks/<n>.json5` | idem | idem |
| S5 mapas | `.swarm/knowledge/tree.json5`, `stack.json5` (gerados aqui); `deps.json5`, `collision.json5` (do `cs.py team`, só validados) | idem | idem | idem |
| Skills de estado (14) e do mandato (9) | `.claude/skills/<n>/SKILL.md` | `.cursor/skills/<n>/SKILL.md` | `.github/skills/<n>/SKILL.md` | `.agents/skills/<n>/SKILL.md` |
| Comandos (≤15 / ≤25) | `/salvar-sessao`, `/carregar-sessao`, `/corrigir`, `/feature-autonoma`, `/planejar-sprint` como skills com `disable-model-invocation: true` | linhas de terminal no S0 | linhas de terminal no S0 | linhas de terminal no S0 |

**Skills de estado (14) e do mandato (9).** As 23 skills finas (só chamam `.swarm/bin/cs-state <sub>` /
`.swarm/bin/cs-auto <sub>`) saem para as 4 plataformas, arquivo inteiro gerado (marcador de gerado), `name` = diretório.
Política de invocação: as que mudam estado (humanas) levam `disable-model-invocation: true` em Claude Code, Cursor e
Copilot; o Codex não tem o campo, então o corpo da skill humana abre com "Só o humano executa" (o guard continua
bloqueando o comando). As de consulta/criação ficam invocáveis pelo modelo e **não** podem dizer essa frase.

Medida de orçamento: linhas não vazias que não são comentário HTML de linha inteira, sem frontmatter.
Termos e regras de negócio entram no S1 como top-N (5→1) por relevância ao território; o restante vai
para S2 até o orçamento e depois só por `cs-mem search`. Conteúdo escrito à mão que estoura a camada
faz a emissão **falhar** com a sugestão de para onde mover.

## 3. Decisões de mapeamento

- **Modelo**: Claude Code sempre `model: inherit` (o tier é decidido por despacho via `cs-route`);
  exceção: gate com piso em `.swarm/routing.json5` (`floors.<agente>`, `agents.<agente>.floor`
  ou `gate_floor`). Cursor `model: inherit`. Copilot/Codex: sem `model` (herda).
- **Gate sem escrita, em toda plataforma**: Claude `tools` sem Edit/Write + `disallowedTools: Edit,
  Write, MultiEdit, NotebookEdit` (isso também impede o agente de escrever na própria memória do Claude
  Code; lições do gate vão por `cs-mem add` via Bash); Cursor `readonly: true`; Copilot sem `edit`;
  Codex `sandbox_mode = "read-only"`.
- **Ferramentas Copilot**: Read/NotebookRead→`read`, Grep/Glob→`search`, Edit/Write→`edit`,
  Bash→`execute`, WebFetch/WebSearch→`web`.
- **Globs**: Claude recebe a lista como está; Cursor e Copilot recebem string com vírgulas e chaves
  expandidas (`*.{ts,tsx}` → `*.ts,*.tsx`), porque a vírgula é o separador deles.
- **Sessão**: `/carregar-sessao` usa `` !`.swarm/bin/cs-session load` `` para injetar o briefing sem o modelo ler
  arquivos; o hook `SessionStart` opcional (`cs-session load --brief`) é instalado pelo harness.
- **Nomes**: arquivos gerados de regra levam prefixo `cs-` para não colidir com regras humanas;
  agentes usam o `name` exato.

## 4. Garantias de escrita

Idempotente (mesma entrada → mesmos bytes; sem timestamp). Arquivo inteiro gerado leva o marcador
`codebase-specialists:generated`; arquivo humano no mesmo caminho = **conflito** (nada é escrito;
proposta + diff em `.swarm/emit/conflicts/`; `--force` faz backup + diff e sobrescreve). Arquivos
compartilhados (`CLAUDE.md`, `AGENTS.md`, `copilot-instructions.md`) só têm o bloco
`<!-- codebase-specialists:begin -->`…`<!-- codebase-specialists:end -->` reescrito; primeira inserção
num arquivo humano faz backup + diff em `.swarm/emit/backups/`. Destino symlink ou fora da raiz é
recusado. Manifesto `.swarm/emit/manifest.json5` permite podar artefatos de agentes removidos.

### 4.1 O que é escrito FORA de `.swarm/` (e como o usuário consente)

`cs.py emit --dry-run` lista à parte, no bloco `outside`, toda escrita fora de `.swarm/`. Mostre esse bloco
ao usuário **antes** de emitir; só com o OK dele rode `cs.py emit --allow-outside`. Sem `--allow-outside`, um
emit que escreveria fora sai com **exit 3** e a lista (nada é escrito fora). Dentro de `.swarm/` nunca
precisa de consentimento. O `harness install` segue a mesma regra: `cs.py harness install --dry-run` lista o
seu bloco `outside` (linhas `harness install` da tabela abaixo) e só `cs.py harness install --allow-outside` escreve
fora de `.swarm/`.

| Quem escreve | Caminho fora de `.swarm/` | Tipo | Desliga com |
|---|---|---|---|
| `emit` (Claude Code) | `CLAUDE.md` (bloco gerenciado), `.claude/agents/<n>.md`, `.claude/rules/cs-<n>.md`, `.claude/skills/<n>-playbooks/`, `.claude/orchestrator.md`, comandos e as 23 skills de estado/mandato em `.claude/skills/` | bloco / arquivo gerado | `--platforms` sem `claude-code` |
| `emit` (Cursor) | `.cursor/rules/cs-*.mdc`, `.cursor/agents/<n>.md`, `.cursor/skills/<n>/SKILL.md` | arquivo gerado | `--platforms` sem `cursor` |
| `emit` (Copilot) | `.github/copilot-instructions.md` (bloco), `.github/agents/<n>.agent.md`, `.github/instructions/cs-<n>.instructions.md`, `.github/skills/<n>/SKILL.md` | bloco / arquivo | `--platforms` sem `copilot` |
| `emit` (Codex) | `AGENTS.md` raiz (bloco), `<dir>/AGENTS.md` aninhado, `.codex/agents/<n>.toml`, `.agents/skills/<n>/SKILL.md` | bloco / arquivo | `--platforms` sem `codex` |
| `harness install` | `.claude/settings.json` (merge + backup), `.claude/hooks/cs-guard.sh` | merge / arquivo | `--no-settings` |
| `harness install` | `specialists.mk` + bloco `include specialists.mk` no `Makefile` | arquivo / bloco | `--no-makefile` |
| `harness install --git-hook` | hook `pre-commit` do git (chama `.swarm/bin/cs-precommit`) | arquivo | omitir `--git-hook` |

### 4.2 Globs — sempre entre aspas

Em todo comando (SKILL, prompts, playbooks, `check`), glob vai entre aspas: o zsh expande `**` sem aspas
(ou falha com "no matches found") e o comando recebe a lista de arquivos em vez do padrão.

| Certo | Errado |
|---|---|
| `cs.py team roster move "src/billing/**" --to dev-billing` | `cs.py team roster move src/billing/** --to dev-billing` |
| `cs.py team roster add dev-web --kind dev --territory "apps/web/**"` | `… --territory apps/web/**` |
| `rg -l "Money" "src/**/*.py"` | `rg -l Money src/**/*.py` |

Dentro de arquivos (frontmatter `globs`/`applyTo`/`paths`, `territory` do `team.json5`) o glob é dado, não
passa pelo shell: o formato de cada plataforma está na §1.

### 4.3 O que `emit validate` confere nas skills

Para cada plataforma pedida: **skill faltando** (falta a saída ou ela difere do que o emit geraria); **política
removida à mão** (skill humana sem `disable-model-invocation: true` em Claude/Cursor/Copilot, ou sem "Só o humano
executa" no Codex; skill de consulta/criação marcada como humana); frontmatter com chave fora do conjunto da
plataforma; e **órfão** (arquivo com marcador de gerado em `.cursor/skills`, `.github/skills`, `.agents/skills` etc.
sem skill correspondente). Sai com exit ≠ 0 citando o caminho.

## 5. Limitações conhecidas

- O Cursor lê `.claude/agents/` e `.codex/agents/` além de `.cursor/agents/`: emitindo as três, o mesmo
  agente aparece em mais de um diretório (a doc não define precedência entre eles). Se incomodar,
  emita o Cursor com `--platforms cursor` sozinho ou remova as outras.
- `AGENTS.md` aninhado é lido por Codex, Copilot e Cursor; com várias plataformas, o S2 do território
  chega a esses agentes por dois caminhos (regra nativa + `AGENTS.md`).
- Os comandos `cs-state`, `cs-mem`, `cs-session` e `cs-route` e suas flags são do harness; o emissor
  só os cita (templates em `assets/templates/`). Se o harness mudar uma flag, ajuste o template.
