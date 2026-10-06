# codebase-specialists — projeto de desenvolvimento

Este repositório é o **projeto completo** da skill `codebase-specialists` para o
[Claude Code](https://claude.com/claude-code): a skill que monta, para qualquer repositório, um time de agentes
especialistas que conhece o código — e prova que conhece (scan com evidência mecânica, entrevista curta, agentes
com território, sonda de maestria, harness com estado, gates, guards e memória; emite para Claude Code, Cursor,
GitHub Copilot e Codex). O que a skill faz e como usá-la num alvo: [`SKILL.md`](SKILL.md),
[`MODO-DE-USO.md`](MODO-DE-USO.md) e [`docs/`](docs/README.md).

Versão: **0.9.0** (ver [`VERSION`](VERSION)).

**Projeto ≠ pacote.** O projeto tem tudo do desenvolvimento (testes, fixtures de avaliação, campanhas, harness de
desenvolvimento). O **pacote** — só o que roda — é gerado por `bash .claude/tools/package.sh` em `dist/`
(gitignored) e validado instalando-o num HOME temporário.

## Estrutura

| Caminho | O quê |
|---|---|
| `SKILL.md`, `MODO-DE-USO.md`, `VERSION` | a skill (a raiz do projeto É a skill) |
| `scripts/` | CLI `cs.py` e módulos, cada um com `tests/` |
| `assets/`, `references/` | templates emitidos; contrato técnico, etapas, prompts, migrações, premissas |
| `evals/` | fixtures (py-billing, ts-shop, go-polyglot), corretor e cenários de avaliação |
| `docs/` | documentação (usuário) + documentos internos de desenvolvimento (não vão no pacote) |
| `.claude/` | harness de desenvolvimento: `CLAUDE.md` (regras), `skills/` (rituais), `tools/` (scripts e testes), `state/` (estado do desenvolvimento), `tools/ac/` (motor de campanhas embutido), `package/` (README do pacote) |
| `campanhas/` | oráculos das campanhas (uma por frente de mudança) — ver [`campanhas/README.md`](campanhas/README.md) |
| `local/` | só nesta máquina (gitignored): termos privados, regras de limpeza privadas, cópias de trabalho, portões |
| `dist/` | pacote gerado (gitignored) |

## Como desenvolver

Abra o Claude Code **na raiz do projeto** (`cd <projeto> && claude`) e rode `/load-session`. O hook SessionStart
injeta a âncora (`.claude/tools/carimbo.sh --brief`); as regras estão em [`.claude/CLAUDE.md`](.claude/CLAUDE.md).
Toda mudança no produto passa pelo fluxo de frente: `/new-front` (campanha em `campanhas/<frente>/`, oráculo
separado, aprovação humana pelo script gerado em `local/`) → cópia de trabalho → `portao.sh` (suítes nos 2
Pythons, oráculos, nenhum `def` removido) → `portar.sh` → `conferir-commit.sh` → commit → `/close-front`. Ao
fechar uma versão: `/package`. Para salvar: `/save-session`.

## Instalar a skill a partir do projeto

O Claude Code descobre a skill pelo `SKILL.md` na raiz da pasta em `~/.claude/skills/`. Para usar o projeto como a
skill instalada (sem cópia), crie um link:

```bash
ln -s "$PWD" ~/.claude/skills/codebase-specialists     # rodado na raiz do projeto
```

Ou instale o pacote: `bash .claude/tools/package.sh` e descompacte `dist/codebase-specialists-<VERSION>.zip` em
`~/.claude/skills/`.

## Primeira vez numa máquina nova

1. Python **3.9+** (só biblioteca padrão) e `git`. Os testes rodam com `python3` e `/usr/bin/python3`.
2. Senha das aprovações humanas (motor de campanhas): no **seu terminal** (nunca pelo agente, nunca no chat):
   `python3 .claude/tools/ac/ac.py frase definir` — grava `~/.claude/auto-correcao/frase.json` (só salts e
   verificador). O hook `.claude/tools/ac/hook_aprovacao.py` impede o agente de aprovar por você.
3. Privacidade: crie `local/termos-privados.txt` (um termo por linha; `re:` para regex) e, se for empacotar,
   `local/regras-privadas.json5` (formato em `python3 .claude/tools/publicar_regras.py --help`). Sem eles o
   `guard-privacidade.sh` avisa e usa só padrões genéricos (caminho de usuário, e-mail pessoal).
4. Hooks git do harness (pre-commit e commit-msg com o guard de privacidade):
   `sh .claude/tools/instalar-hooks-git.sh`.
5. Âncora: `bash .claude/tools/carimbo.sh`.

## Testes

```bash
# suítes da skill (cada módulo de scripts/ e evals/)
R="$PWD"; for d in scripts/*/tests evals/tests; do (cd "${d%/tests}" && CS_SKILL_DIR="$R" python3 -m unittest discover -s tests); done
# harness de desenvolvimento
(cd .claude/tools && python3 -m unittest discover -s tests)
```

## Limites

- Testes que precisam de recurso privado **pulam com motivo** quando a variável não está definida:
  `$CS_UPGRADE_LEGACY_TARGET` (alvo gerado por versão anterior da skill), `$CS_V8_REPO_SRC` (repositório git com um
  harness v8 instalado), `$CS_TS_SHOP_TARGET` (alvo ts-shop com harness instalado) e, nos oráculos,
  `$CS_PILOTO_SRC` (repositório-piloto legado).
- O histórico mecânico das campanhas antigas (ledger `.auto-correcao/`) ficou na máquina original; aqui ficam os
  oráculos e a tabela em `campanhas/README.md`.
- Os hooks do harness são filtros sintáticos, não sandbox (ver "O que NÃO existe" em `.claude/CLAUDE.md`).

## Licença

[MIT](LICENSE).
