# codebase-specialists

Skill do [Claude Code](https://claude.com/claude-code) que monta, para qualquer repositório, um **time de agentes
especialistas que conhece o código** — e prova que conhece.

- **Scan com evidência mecânica**: estrutura, convenções reais, regras técnicas e de negócio, glossário, histórico
  git, decisões (ADRs), comandos executados e versões exatas da stack. Cada fato aponta `arquivo:linha`.
- **Entrevista curta** com o dono do repositório, só no que o código não diz.
- **Agentes com território de escrita limitado** e cartão de conhecimento derivado dos fatos.
- **Sonda de maestria** com gabarito gerado por script: o agente é examinado sobre o repositório e só sai
  `especialista` se passar.
- **Harness** instalado no alvo: estado em JSON5, gates, guards de escrita, memória com busca BM25 e sessão
  retomável.
- Emite para **Claude Code, Cursor, GitHub Copilot e Codex/AGENTS.md**; as skills de estado (`/auto-*` e demais)
  também são geradas para Cursor, Copilot e Codex.
- **Modo autônomo (`cs-auto`)**: mandato com orçamento e corte, máquina de estados, ramo travado, pausa e portão
  humano (ver [`docs/11-modo-autonomo.md`](docs/11-modo-autonomo.md)).

Versão: **0.8.0** (ver [`VERSION`](VERSION)).

## Requisitos

- Python **3.9+** (apenas biblioteca padrão; nada para instalar via pip).
- `git`.
- Claude Code (para o fluxo guiado pela skill). A CLI `scripts/cs.py` também roda sozinha.

## Instalação

Clone (ou copie) este repositório para a pasta de skills do Claude Code:

```bash
git clone <url-deste-repositorio> ~/.claude/skills/codebase-specialists
```

O Claude Code descobre a skill pelo `SKILL.md` na raiz da pasta.

## Uso

Numa sessão do Claude Code aberta **no repositório-alvo** (com `git status` limpo):

```text
/codebase-specialists            # monta o time no modo padrão (rápido)
/codebase-specialists --full     # modo certificado (mesa redonda + refino)
/codebase-specialists status     # onde a execução está; não altera nada
/codebase-specialists retomar    # continua de onde parou
/codebase-specialists upgrade    # plano de atualização de um time já instalado
```

Também funciona em linguagem natural ("monta o time de agentes pra esse repo").

O guia completo — toques com você, o que é escrito no repositório, retomada, upgrade e convivência com outro
harness — está em [`MODO-DE-USO.md`](MODO-DE-USO.md). A documentação detalhada fica em [`docs/`](docs/README.md).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `SKILL.md` | instruções que o Claude Code segue |
| `references/` | contrato técnico (`ARCHITECTURE.md`), etapas, prompts, premissas com fontes |
| `scripts/` | CLI `cs.py` e módulos (scan, team, probes, emit, harness, memory, verify, upgrade...) com testes |
| `assets/templates/` | templates dos artefatos emitidos |
| `evals/` | fixtures (py-billing, ts-shop, go-polyglot), corretor e cenários de avaliação |
| `docs/` | documentação para humanos |

## Testes

```bash
cd scripts
for d in */tests; do (cd "${d%/tests}" && python3 -m unittest discover -s tests); done
```

Alguns cenários dependem de artefatos externos opcionais e são **pulados** quando eles não existem:
`$CS_UPGRADE_LEGACY_TARGET` (alvo gerado por uma versão anterior da skill), `$CS_V8_REPO_SRC` (repositório git
com um harness v8 instalado) e `$CS_TS_SHOP_TARGET` (alvo ts-shop com harness já instalado).

## Licença

[MIT](LICENSE).
