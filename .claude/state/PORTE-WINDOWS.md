# PORTE-WINDOWS — o que levar da `release/desenv-mac` para a branch Windows

Registro de TODA melhoria do produto feita nesta máquina (macOS) que precisa ir para a versão Windows.
Pedido do founder (2026-10-08). Atualizado a cada feature entregue (commit de produto) — quem fecha a feature
acrescenta a seção dela aqui antes do `/salvar-sessao`.

## Como portar (recomendação)

1. Uma versão por vez, na ordem abaixo (cada uma tem migração no `references/migrations.json5` que depende da
   anterior).
2. `git cherry-pick <commit>` SÓ dos commits de PRODUTO listados (nunca os `state:` nem `harness:` — `.claude/` é o
   harness de desenvolvimento desta máquina).
3. Conflito ⇒ resolva preservando a adaptação Windows; rode as suítes (`scripts/*/tests`, `evals/tests`) e o oráculo
   da campanha (`campanhas/<id>/oraculo/`) no Python da máquina Windows.
4. Confira os "riscos Windows" de cada item — o produto nunca foi testado em Windows; os pontos sensíveis estão
   marcados.

Pontos sensíveis gerais do produto em Windows (valem para todas as versões):
- lock por `fcntl` não existe (cai para execução em série: `hcore.py:302`, `mem.py:146`);
- `install.py` liga o pre-commit por **symlink** (`os.symlink`, `install.py:~386`) — em Windows exige modo
  desenvolvedor ou admin; sem isso, copiar o hook;
- hooks git são `#!/bin/sh` (`.swarm/bin/cs-precommit`) — funcionam no Git for Windows (bash embutido);
- caminhos: o motor normaliza para `/` (`hcore.norm_rel`); conferir onde há `os.sep`;
- scripts do harness de desenvolvimento (`.claude/tools/*.sh`, `/usr/bin/python3` como 2º Python) são desta máquina —
  não vão para o Windows.

---

## 0.10.0 — iter18 · commit `5e8f6b2` (2026-10-06) · origem: uso real na segunda cobaia .NET

| # | Melhoria | Arquivos |
|---|---|---|
| R1 | `tree_sha256` só sobre arquivos rastreados ou não ignorados (`git ls-files -co --exclude-standard`): bin/obj de uma task não invalidam o accept de outra | `scripts/harness/engine/engine.py`, `cmds.py` |
| R2 | `reverify` a partir de VERIFIED/REVIEWED quando a árvore mudou; reviews preservadas se os files_changed não mudaram | `machines.json5`, `engine.py`, `cmds.py`, `views.py`, `tests/test_cobertura_maquinas.py` |
| R3 | cartão do gate manda o gate registrar o próprio `cs-state review` | `scripts/emit/render.py` |
| R4 | kernel do orquestrador proíbe ditar o veredito ao gate | `assets/templates/orchestrator.md` |
| R5 | pre-commit (`--staged`) barra allowed_paths de task com delegação não ACCEPTED | `scripts/harness/engine/guard.py` |
| R6 | bashscan: `git check-ignore/ls-remote/count-objects` são somente leitura | `scripts/harness/engine/bashscan.py` |
| R7 | allowed_paths = território inteiro recusado no check/start; `amend` em item da árvore não iniciado | `engine.py`, `state.py`, `tree.py` |
| R8 | versão 0.10.0 + migração harness+emit | `VERSION`, `README.md`, `references/migrations.json5`, `docs/09-upgrade.md` |

Testes: `scripts/harness/tests/test_iter18_a_escopo.py`, `test_iter18_b_bashscan.py`, `test_iter18_b_precommit.py`;
oráculo `campanhas/iter18/oraculo/`.
Riscos Windows: R1 chama `git ls-files -z` (ok no Git for Windows); `git check-ignore` idem.

## 0.10.1 — iter20 · commit `97a1718` (2026-10-07) · B-13

| # | Melhoria | Arquivos |
|---|---|---|
| U1–U4 | pre-commit aceita o resultado do próprio `upgrade --apply`/`emit`/`harness install` por **atestado** (sha256 por arquivo escrito, ancorado no ledger encadeado); edição/remoção à mão continua barrada; `--no-renames` (remoção do motor não passa como renomeação para o backup) | `scripts/harness/engine/attest.py` (novo), `guard.py`, `scripts/harness/install.py`, `scripts/harness/cli.py`, `scripts/emit/apply.py`, `scripts/emit/cli.py` |
| — | install grava `.swarm/harness/.gitignore` com `__pycache__/` | `scripts/harness/install.py` |
| U5 | versão 0.10.1 (0.9.0 → 0.10.1 aplica as duas migrações) | `VERSION`, `README.md`, `references/migrations.json5`, `docs/09-upgrade.md` |

Testes: `scripts/harness/tests/test_iter20_atestado.py`; oráculo `campanhas/iter20/oraculo/`.
Riscos Windows: o atestado mora em `<git-dir>/codebase-specialists/atestado.json` (usa `git rev-parse --git-dir`);
sha256 é sobre BYTES — **atenção a `core.autocrlf`**: se o Git converter CRLF no checkout/stage, o sha do blob staged
pode divergir do que a ferramenta gravou ⇒ o commit do upgrade seria barrado. Recomendado no alvo Windows:
`git config core.autocrlf false` (ou `.gitattributes` com `* -text` para `.swarm/**` e artefatos emitidos) e testar o
U1 do oráculo iter20 lá.

## 0.11.0 — iter19 · EM ANDAMENTO (feature `iter19`, B-14)

Estado de entidades em JSON padrão (ordem de leitura, indent 2, chaves em inglês, `_generated_by`), `amend` refletido
no arquivo (e no `history` com before/after/reason), `cs-state show`, `cs-state find` terminando no caminho, validate
estrito para `.json`, migração automática no `upgrade` por evento encadeado novo. Arquivos e commit entram aqui no
fechamento. Riscos Windows previstos: escrita de `.json` com `\n` (o motor grava com newline explícito — conferir que
não vira CRLF, ver `core.autocrlf` acima); renomeação `.json5`→`.json` em disco.

## 0.12.0 — iter21 · EM ANDAMENTO (memória dos agentes: B-22, B-23, B-24, M12, M13)

Caderno `.claude/agent-memory/<agente>/MEMORY.md` (bloco gerado pelo cs-mem + área livre), guard/pre-commit do
caderno, brief com memória reservada e busca relevante, rastro de buscas, `consultei:`, `/correct` com "quem errou",
supersede/retract, `check` sem `--files`. Riscos Windows previstos: o caderno só existe no Claude Code (igual em
Windows); `--paths` com globs usa `/`; a prova real (`campanhas/iter21/oraculo/prova_real.py`) chama `claude -p` — no
Windows conferir o binário e o stream-json.

## Pendentes no BACKLOG que também afetarão o Windows

B-19 (descarte de task não iniciada), B-21 (chaves do mandato em inglês), B-25, B-26, B-27, B-28 (`cs-state add` →
`new` nos textos emitidos).
