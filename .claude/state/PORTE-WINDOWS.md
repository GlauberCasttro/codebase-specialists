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

## 0.11.0 — iter19 · commit `c2b74ae` (2026-10-11) · B-14

Estado de entidades em JSON padrão (ordem de leitura, indent 2, chaves em inglês com aliases pt na leitura,
`_generated_by`), `amend` refletido no arquivo no mesmo evento (`history` com before/after/reason), `cs-state show`,
`cs-state migrate state-format [--dry-run]` (um evento `arvore.format` com o mapa de caminhos; idempotente) e a ação
`state-format` no `cs.py upgrade --apply` (validate --strict antes/depois, backup restaurado em falha).
Arquivos para cherry-pick (23): `scripts/harness/engine/{auto,autonomy,cmds,hcore,selftest,session,state,tree,validate}.py`,
`scripts/harness/tests/{test_iter19_estado,test_iter20_atestado}.py`, `scripts/upgrade/{core,version}.py`,
`scripts/upgrade/tests/test_iter19_upgrade.py`, `VERSION`, `README.md`, `references/{migrations.json5,ARCHITECTURE.md}`,
`docs/{01-conceitos,05-sessao-e-retomada,06-referencia-cli,09-upgrade,10-arvore-de-estado}.md`.
Riscos Windows: escrita de `.json` com `\n` explícito (conferir que não vira CRLF com `core.autocrlf`); renomeação
`.json5`→`.json` em disco (arquivo aberto no editor pode travar o rename); oráculos iter18 R8 / iter20 U5 fixam versão
(B-32) — rodar só R1–R7 e U1–U4.

## 0.12.0 — iter21 · commit `7fdb431` (2026-10-12) · B-22, B-23, B-24, B-27

Caderno `.claude/agent-memory/<agente>/MEMORY.md` (bloco gerado pelo cs-mem + área livre), guard/pre-commit do caderno
(só o dono, só fora do bloco; bloco aceito só se igual ao render do cs-mem), brief com memória reservada e termos por
relevância, rastro de buscas com dono, `consultei:` conferido, `/correct` com "quem errou", prévia e confirmação,
supersede/retract, upgrade que regenera os cadernos. Oráculos de versão relativos (B-32).
Arquivos para cherry-pick (24): `scripts/memory/mem.py` + `scripts/memory/tests/{test_iter21_ciclo2,test_iter21_memoria,test_iter21_r1,test_mem}.py`,
`scripts/harness/engine/{brief,cmds,guard,hcore,state,views}.py`, `scripts/harness/tests/test_iter21_motor.py`,
`scripts/upgrade/core.py`, `scripts/upgrade/tests/test_iter19_upgrade.py`, `scripts/emit/platforms.py`,
`scripts/emit/tests/test_iter21_emit.py`, `assets/templates/{correct,memory}.md`, `docs/{03-memoria-e-licoes,06-referencia-cli,09-upgrade}.md`,
`references/migrations.json5`, `VERSION`, `README.md`; e os oráculos `campanhas/iter18..21`.
Riscos Windows: CRLF no caderno é normalizado no pre-commit (testado por bytes, não com `core.autocrlf` real);
NOTEBOOK_RE case-insensitive e symlink divergente recusado (no Windows conferir junction/`\`); `--paths` com globs usa
`/`; a prova real chama `claude -p` (conferir o binário e o stream-json).

## 0.12.1 — iter22 · commit `da30e17` (2026-10-12) · B-35

`cs-state show` liberado no guard (STATE_SUB main e any) + varredura argparse × guard (subcomando sem regra reprova).
Arquivos para cherry-pick: `scripts/harness/engine/guard.py`, `scripts/harness/tests/test_iter22_*.py`,
`scripts/emit/tests/test_iter21_emit.py`, `references/migrations.json5`, `docs/09-upgrade.md`, `VERSION`, `README.md`;
oráculo `campanhas/iter22`. Riscos Windows: nenhum novo (só lista de subcomandos).

## 0.12.2 — iter24 · commit `b757d1f` (2026-10-13) · B-44, B-45, B-46, B-47 (parcial)

Hotfix de segurança do guard: harness por `sh|bash`, `python3 -m`, `-W/-X`, `cd .swarm/harness` e caminho por
variável/`~` (normpath antes do regex); `ln`/`cp -l` e escrita por hardlink (nlink>1) de protegido; registros humanos
(approvals.jsonl, team-approvals.jsonl, acceptance.json5, run.json5, team.json5) não graváveis; destinos de `--output=`,
`-o`, `-O`, `-C`, `-d`; inline com flags combinadas e stdin fail-closed; git que desliga hooks / push forçado ou
protegido / branch -D protegida / remote set-url|add / reflog expire.
Arquivos para cherry-pick (10): `scripts/harness/engine/{bashscan,guard,hcore,auto}.py`,
`scripts/harness/tests/{test_iter24_guard,test_guards}.py`, `references/migrations.json5`, `docs/09-upgrade.md`,
`VERSION`, `README.md`; oráculo `campanhas/iter24`.
Riscos Windows (o bashscan modela shell POSIX): `os.path.normpath` no Windows troca `/` por `\` — o regex
`\.swarm/(harness|bin)/` precisa de `posixpath.normpath` ou de casar os dois separadores; hardlink no NTFS existe
(`st_nlink` funciona em Python 3.9+), mas `os.walk` com junctions pode laçar; FS case-insensitive (B-55: `.SWARM`,
`:MAIN`) é o padrão no Windows — tratar caixa antes de portar; comandos PowerShell (`Copy-Item`, `New-Item
-ItemType HardLink`, `Out-File`) não são modelados.

## 0.13.0 — iter23 · commit `933012d` (+ `1d3d78d` oráculo iter10) (2026-10-14) · B-19, B-28, B-39..B-43, B-59, B-60

Fluxo da árvore: `drop`/`amend` de task não iniciada, sprint fecha com DROPPED, uma sprint aberta por épico, DoR
estático no `new task`, `plan <story> --sprint`, textos emitidos e Makefile com `new`/`plan`/`drop` (`new-epic`),
auto-memória do Claude Code liberada ao principal, `cs-state version` + `version` no MANIFEST, upgrade que aponta
itens presos.
Arquivos para cherry-pick (26): `scripts/harness/engine/{tree,state,guard,hcore,validate}.py`,
`scripts/harness/tests/{test_iter23_arvore,test_iter19_estado}.py`, `scripts/harness/install.py`,
`scripts/emit/{render,platforms}.py`, `scripts/emit/tests/test_iter23_emit.py`,
`assets/templates/{orchestrator,product-process,plan-sprint}.md`, `docs/{02-harness,06-referencia-cli,09-upgrade}.md`,
`references/{harness.md,ARCHITECTURE.md,migrations.json5}`, `scripts/upgrade/core.py`,
`scripts/upgrade/tests/test_iter23_upgrade.py`, `VERSION`, `README.md`; oráculos `campanhas/iter23` e a mudança
oficial em `campanhas/iter10`.
Riscos Windows: o slug da auto-memória é derivado do realpath com todo [^A-Za-z0-9] → '-' (no Windows o caminho tem
`C:\` — conferir como o Claude Code nomeia a pasta lá antes de portar o `in_auto_memory`); `os.lstat().st_nlink`
funciona no NTFS (Python 3.9+); `stuck_items` roda `sys.executable -I -c` com o caminho do alvo em argv (sem shell —
ok com espaços); `HOME` vs `USERPROFILE` para achar `~/.claude/projects/`.

## 0.13.1 — iter25 · commit `633a307` (+ `bac0e0f` oráculo iter23) (2026-10-17) · B-64

Cada item da árvore grava o `status` canônico em inglês (TODO/BACKLOG/ACTIVE/DONE/DROPPED e o par M2), derivado de
`tree.status_code`; validate confere; upgrade com a ação `item-status` (`cs-state migrate item-status`).
Arquivos para cherry-pick: `scripts/harness/engine/{tree,hcore,engine,state}.py`,
`scripts/harness/tests/test_iter25_status.py`, `scripts/upgrade/{core,version}.py`,
`scripts/upgrade/tests/test_iter25_upgrade.py`, `references/migrations.json5`, `docs/{09-upgrade,10-arvore-de-estado}.md`,
`VERSION`, `README.md`; oráculo `campanhas/iter25` e a mudança oficial 02 em `campanhas/iter23`.
Riscos Windows: regravação de arquivos de item (fim de linha CRLF vs LF no texto comparado para "só regrava se mudou").

## 0.14.0 — iter26 · commit `8401adc` (+ oráculos `244006a`, `d12e026`, `58ebdc9`, `e920288`) (2026-10-19) · B-49, B-67

Sem campos mortos nas tasks; `kind: "epic"`; `repro_steps`; CLI/templates/docs em inglês com aliases pt depreciados;
`rejections`/`gate_history` por tentativa; `delegation.usage` (tokens do transcript) no guard; verify aceita o caderno
regravado pelo harness; `close` e orquestrador citam o `git add .swarm`.
Arquivos para cherry-pick (39): lista em `.claude/state/archive/iter26/iter26.md` (seção Arquivos da feature).
Riscos Windows: o guard lê o transcript do subagente inteiro linha a linha (caminho com `\` e encoding UTF-8 explícito);
o verify compara a área livre do caderno com `git show HEAD:<caminho>` (separador `/` no pathspec do git);
`git add -A .swarm` no texto emitido vale igual no Windows.

## Pendentes no BACKLOG que também afetarão o Windows

B-19 (descarte de task não iniciada), B-21 (chaves do mandato em inglês), B-25, B-26, B-27, B-28 (`cs-state add` →
`new` nos textos emitidos).
