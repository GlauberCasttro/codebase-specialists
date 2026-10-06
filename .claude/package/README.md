# codebase-specialists

Skill do [Claude Code](https://claude.com/claude-code) que monta, para qualquer repositório, um **time de agentes
especialistas que conhece o código** — e prova que conhece.

- **Scan com evidência mecânica**: estrutura, convenções reais, regras técnicas e de negócio, glossário, histórico
  git, decisões (ADRs), comandos executados e versões exatas da stack. Cada fato aponta `arquivo:linha`.
- **Entrevista curta** com o dono do repositório, só no que o código não diz.
- **Agentes com território de escrita limitado** e cartão de conhecimento derivado dos fatos.
- **Sonda de maestria** com gabarito gerado por script: o agente é examinado sobre o repositório e só sai
  `especialista` se passar.
- **Harness** instalado no alvo: estado em árvore de pastas, gates, guards de escrita, memória com busca BM25 e
  sessão retomável.
- Emite para **Claude Code, Cursor, GitHub Copilot e Codex/AGENTS.md**; as skills de estado (em inglês,
  verbo-objeto: `load-session`, `save-session`, `plan-sprint`, `new-epic`…) também são geradas para Cursor, Copilot
  e Codex.
- **Modo autônomo (`cs-auto`)**: mandato com orçamento e corte, máquina de estados, ramo travado, pausa e portão
  humano com senha (ver [`docs/11-modo-autonomo.md`](docs/11-modo-autonomo.md)).

Versão: **{{VERSION}}** (ver [`VERSION`](VERSION)). Este é o **pacote** (só o que roda). O desenvolvimento — testes,
fixtures de avaliação, campanhas e harness de desenvolvimento — fica no repositório do projeto.

## Requisitos

- Python **3.9+** (apenas biblioteca padrão; nada para instalar via pip).
- `git`.
- Claude Code (para o fluxo guiado pela skill). A CLI `scripts/cs.py` também roda sozinha.

## Instalação

Descompacte (ou copie) esta pasta para a pasta de skills do Claude Code:

```bash
unzip codebase-specialists-{{VERSION}}.zip -d ~/.claude/skills/
# resultado: ~/.claude/skills/codebase-specialists/SKILL.md
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
| `references/` | contrato técnico (`ARCHITECTURE.md`), etapas, prompts, migrações, premissas com fontes |
| `scripts/` | CLI `cs.py` e módulos (scan, team, probes, emit, harness, memory, verify, upgrade...) |
| `assets/templates/` | templates dos artefatos emitidos |
| `docs/` | documentação para humanos |

## Licença

[MIT](LICENSE).
