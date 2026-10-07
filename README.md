# codebase-specialists — projeto de desenvolvimento

Este repositório é o **projeto completo** da skill `codebase-specialists` para o
[Claude Code](https://claude.com/claude-code): a skill que monta, para qualquer repositório, um time de agentes
especialistas que conhece o código — e prova que conhece (scan com evidência mecânica, entrevista curta, agentes
com território, sonda de maestria, harness com estado, gates, guards e memória; emite para Claude Code, Cursor,
GitHub Copilot e Codex). O que a skill faz e como usá-la num alvo: [`SKILL.md`](SKILL.md),
[`MODO-DE-USO.md`](MODO-DE-USO.md) e [`docs/`](docs/README.md).

Versão: **0.10.0** (ver [`VERSION`](VERSION)).

**Projeto ≠ pacote.** O projeto tem tudo do desenvolvimento (testes, fixtures de avaliação, campanhas, harness de
desenvolvimento). O **pacote** — só o que roda — é gerado por `bash .claude/tools/package.sh` em `dist/`
(gitignored) e validado instalando-o num HOME temporário; é ele a skill instalada nesta máquina (`/install`).

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
fechar uma versão: `/package`; atualizar a skill instalada: `/install`. Para salvar: `/save-session`.

## Instalar a skill a partir do projeto

A skill **instalada** nesta máquina é o **pacote** (`dist/codebase-specialists`), não o projeto inteiro. No Claude
Code aberto na raiz do projeto, rode `/install` (`.claude/tools/instalar.sh`): instala as travas do git, gera e
valida o pacote (só troca o pacote anterior se a validação passar) e liga `~/.claude/skills/codebase-specialists` →
`dist/codebase-specialists`; o que houver lá antes vai para `~/.claude/skills-backup-<data>/` (nunca é apagado).
`--dry-run` mostra o plano; `--check` diz se está em dia. O SessionStart avisa quando o pacote instalado ficou
desatualizado (commit de produto depois do pacote) e sugere `/install`; o `/close-front` manda rodar `/install`
depois do commit da frente.

## Primeira vez numa máquina nova

Você não digita comando de terminal: pede ao Claude, e as skills do projeto fazem o resto.

1. A máquina precisa de Python 3.9+ (só biblioteca padrão) e git.
2. Clonar: num Claude Code aberto em qualquer pasta, peça "clone o repositório codebase-specialists em
   ~/Repositorios".
3. Abrir: abra o Claude Code na pasta do projeto clonado (os hooks e as regras do harness só valem ali).
4. Rode `/install`: instala as travas do git (guard de privacidade no commit), gera e valida o pacote e liga a skill
   instalada ao pacote, com backup do que houver lá.
5. Rode `/load-session`: o Claude mostra onde o desenvolvimento parou e a próxima ação.
6. Senha das aprovações humanas (motor de campanhas): é sua e só sua. Quando uma aprovação pedir, defina-a no
   **seu terminal** (nunca pelo agente, nunca no chat) com `python3 .claude/tools/ac/ac.py frase definir` — grava só salts e verificador em `~/.claude/auto-correcao/frase.json`; o hook de aprovação impede o agente de aprovar por você.
7. Privacidade: peça ao Claude para criar `local/termos-privados.txt` (um termo por linha; `re:` para regex) e, se
   for empacotar, `local/regras-privadas.json5`. Sem eles o guard de privacidade avisa e usa só padrões genéricos
   (caminho de usuário, e-mail pessoal).

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
