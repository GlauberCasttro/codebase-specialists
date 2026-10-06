# Pontos do founder — registro único (não perder)

Todo pedido, decisão e problema trazido pelo founder sobre a `codebase-specialists` (e a `auto-correcao`), com status
e onde está. Atualizar este arquivo a cada ponto novo. Última atualização: 2026-10-05.

Legenda de status: ✅ feito · 🔧 em andamento · 📄 especificado (aguarda rodada) · 🧪 desenho (aguarda aprovação) · ⏳ pendente de decisão

## Checklist (atualizar a cada passo)

### ✅ Feito
- [x] Skill `codebase-specialists` construída e refinada em 4 iterações de evals (qualidade 13/13 vs baseline 9–10/13)
- [x] `--fast` como modo padrão; `--full` sob pedido
- [x] Comando acionável `/codebase-specialists [--full|status|retomar|uso]` + `MODO-DE-USO.md`
- [x] Documentação completa com diagramas das duas skills (`docs/`)
- [x] Skill global `auto-correcao` v0.2 + documentação; lições L15/L16
- [x] Três faixas de interação (consulta só-leitura, task avulsa, fluxo completo) — implementado e testado (6/6; 480 testes nos 2 Pythons)
- [x] Revisão de regressão das 3 faixas: nenhuma máquina, transição, guarda ou função removida
- [x] Oráculo de vivacidade das máquinas escrito (falhando hoje, como esperado)
- [x] Pesquisa e desenho do novo modo autônomo (`docs/AUTONOMIA-DESENHO.md`)
- [x] repositório-piloto (projeto-legado) limpo (91 MB de lixo removidos; `.gitignore`); evidência guardada
- [x] Ajuste do founder no `cs-precommit` commitado
- [x] Roadmaps da próxima rodada e da seguinte escritos e versionados; registro único (este arquivo)
- [x] repo v8: forense + time de 11 agentes especializados, enviados na `v9-dev`

### ✅ Feito na campanha `campanha-iter5` (commit `6483606`, via auto-correcao, 9 etapas fechadas)
- [x] A1/A2 — ESCALATED/ABSTAINED destravados (retomar, trocar, descartar, `reverify`, `waive-verify` só humano); task sai de BLOCKED; fonte única de estados
- [x] B1 — três faixas (consulta, task avulsa, fluxo completo)
- [x] Atalhos de guarda removidos (feature ativa com épico inativo + 4 outros); validate acusa hierarquia incoerente
- [x] Ondas paralelas: verify não acusa arquivo da task irmã
- [x] `sanitize` (approve.4) · `upgrade` (VERSION 0.5.0 + migrations; legado suportado) · existência em todos os modos (specialize.5) · exame ligado ao hash do cartão
- [x] D6 — oráculos: vivacidade, workflow E2E (20), cobertura (78/80 transições, 71/71 guardas passando e recusando)
- [x] Portão de regressão 10/10 · 617 testes em 3.13 e 3.9.6
- [x] `auto-correcao`: modo "requisito novo" na calibração (L15) e pré-autorização humana condicionada

### ✅ Feito nas campanhas iter6–iter8 e na auto-correcao v0.3 (2026-10-04)
- [x] D-0-13 retry sobre trabalho já na árvore (`10e5439`, campanha-iter6)
- [x] D-1-02 despacho fantasma (`--tool-use-id` ou `--manual`) · D-1-03 protected_paths provados pelo motor (`d4a6c3d`, campanha-iter7, 660 testes)
- [x] D-1-04 hierarquia legada reconhecida por `legacy-ack` humano; `cs-state validate` só-leitura (`35cd16e`, campanha-iter8, 670 testes nos 2 Pythons)
- [x] Cobaia repositório-piloto: motor reinstalado com backup; 2 reconhecimentos do founder; `validate` e selftest G6 verdes
- [x] `auto-correcao` v0.3 (`5800ed2`): remedição real (AC-01), stage correto (AC-02), L02 mecânica (AC-03), aprovação só no terminal com desafio + auditoria + hook global instalado (AC-04), PLANO validado (AC-05), campanhas sobrepostas `overlap` (L17)
- [x] Nova skill `construcao-orquestrada` — pesquisa (evals, loops/grafos, gates), desenho v2 e onda 0 (`5e9e6f7`)

### ✅ Feito nas versões 0.7.0 e 0.8.0 (2026-10-05)
- [x] 0.7.0 — árvore de pastas de estado (épico → sprint → feature → tasks; backlog/state/archive)
- [x] 0.7.0 — 14 skills de estado (`/board`, `/new-*`, `/close-*`, `/reopen`, `/park`, `/move`); as que mudam estado só o humano chama
- [x] 0.7.0 — tipo de task `CHORE` para manutenção técnica
- [x] 0.7.0 — `--dry-run`, `check` e `--json` nos comandos de estado
- [x] 0.8.0 — modo autônomo mandato: `cs-auto propose` → `/auto-approve` com a senha (só o humano) → `tick` … → `report`
- [x] 0.8.0 — upgrade de uso real corrigido: U-3 motivo visível, U-4 selftest não suja alvo legado, U-5 caminhos legados do `team.json5` traduzidos
- [x] 0.8.0 — as 14 skills de estado e as 9 do mandato também saem para Cursor, Copilot e Codex (política humana preservada; `emit validate` confere)
- [x] 0.8.0 — projeto novo já nasce em árvore; `reroute`/`retry` atualizam a task; `next` orienta abrir sessão

### ⏳ Pendente — próxima rodada (`ROADMAP-proxima-rodada.md`, via `/auto-correcao`)
- [ ] Destravar a KEY na cobaia (ajustar verification_command → retry → despacho pelo founder → verify → security → accept) e depois OPS/AGT/QA
- [ ] Pasta `.swarm/` + harness único / `--replace-harness` (SWARM-DIR-1..4) — **campanha-iter9 aberta, oráculo em escrita**
- [ ] Pacotes de entrada por comando (spot-check, core, juízes); caminho único das respostas do exame
- [ ] Medição final da iteração 4 (retomar py-billing e go-polyglot)
- [ ] D-0-12: `feature drop` com stories em andamento (guarda)
- [ ] Prova do sanitize num init completo nas 3 fixtures; evals 4–6 (autônomo, escalada, bugfix)
- [ ] `auto-correcao` v0.4 (não entraram na v0.3): trocar o critério de parada invalida o portão `stop`; `results compare` separa base de remedição; AC-06 `--scope` com vírgulas vira glob único

### ⏳ Pendente — rodada seguinte (`ROADMAP-rodada-seguinte.md`)
- [ ] Árvore de estado: épico → sprint → feature(s) → tasks; backlog/state/archive — **campanha-iter10 aberta; oráculo em escrita em paralelo; correção espera a iter9 (escopos colidem, `overlap`)**
- [ ] Stories simples/compostas; `/new-*`, `/close-*`, `reopen`, `move`, `park`, inferência pela triagem
- [ ] Uma feature ativa por vez; tasks paralelas sem colisão
- [ ] Carimbo de sessão de 8 blocos (`save --check` obrigatório)
- [ ] Migração `state-tree` no upgrade; estudar o v8 como aprendizado

### ⏳ Pendente — depois
- [ ] Aprovação do founder do desenho do modo autônomo → implementação (M5 `mandato`, 28 cenários AUTO-*)
- [ ] Decisão: tipo de task para manutenção técnica (sugestão `CHORE`)
- [ ] D-027 no repo v8 (onde mora o runtime JIT — ADR)

## A. Problemas encontrados em uso real (prioridade sobre tudo)

| # | Ponto | Status | Onde |
|---|---|---|---|
| A1 | **Delegação trancada em ESCALATED** — nenhuma transição sai (reject/retry/reroute/return/accept recusam). 1º relato: TASK-02-001-AGT. | 🔧 | oráculo `scripts/harness/tests/test_maquinas_vivacidade.py`; correção em `machines.json5` + engine: saídas retomar (`retry --decision`), trocar agente (`reroute`), descartar (`drop --reason`); ABSTAINED idem |
| A2 | **Mesmo deadlock com falha de AMBIENTE** — TASK-02-002-KEY: código correto (3/3 ACs, testes passam), `verify` falhou por `httpx` ausente; lead não pode auto-aprovar; S-1 inteira travada (KEY, OPS, QA). Pedido: transição depois que o lead decide. | 🔧 | mesma correção + `cs-state reverify` (roda o verify de novo) + `cs-state waive-verify --by <humano> --reason --evidence` (só para falha de ambiente, nunca de asserção; review continua obrigatória) + `failure_kind: environment` + tabela "delegação escalada → saídas" no kernel |
| A3 | Repositório real com o harness antigo travado precisa receber a correção sem rodar tudo de novo. | ⏳ | após A1/A2: `cs.py harness install --allow-outside` recopia só o motor (preserva board/eventos/memória); definitivo via `upgrade` (C2) |
| A4 | **Lixo após o init** — repositório-piloto (projeto-legado) com 91 MB em `.specialists/tmp/` (15 clones de exame com `.git`) e sem `.gitignore`. | ✅ limpo à mão no repositório-piloto (commit `1e94b49` no repo do founder) · 📄 `sanitize` | `ROADMAP-proxima-rodada.md` §P0 sanitize (SANITIZE-1..4); evidência em `campanhas/evidencias/repositorio-piloto-2026-10-03/` |
| A6 | **Hotfix aplicado pelo founder na cobaia** para destravar a KEY: tirou ESCALATED de terminal; `verify`/`accept`/`reject` a partir de ESCALATED; pares de TASK saindo de BLOCKED; listas hardcoded em `cmds.py`; `httpx` instalado. **Aproveitado:** saída de BLOCKED na máquina da task e listas duplicadas fora do `machines.json5`. **Rejeitado:** REJECTED como terminal (quebraria `retry`/`all_tasks_closed`), `accept`/BLOCKED→ACCEPTED a partir de ESCALATED (pula verify/review), ABSTAINED esquecido. Harness hotfixado tem hash ≠ MANIFEST até reinstalar o motor. | 🔧 insumo enviado à correção A1/A2 | cobaia: repositório do founder (a indicar) |
| A5 | Ajuste do founder no `cs-precommit` (raiz via `git rev-parse` para rodar por symlink). | ✅ | commit `d221e8e` |

## B. Interação com os especialistas e processo de trabalho

| # | Ponto | Status | Onde |
|---|---|---|---|
| B1 | Harness obriga o fluxo inteiro até para perguntar a um especialista ou mudar 1 linha. **Três faixas:** consulta só-leitura (`cs-state ask`), task avulsa (`add task --quick`, trivial/pequena), fluxo completo (feature/risco). | ✅ implementado e testado (6/6 cenários; 480 testes verdes nos 2 Pythons) — commit junto com A1/A2 | `ROADMAP-proxima-rodada.md` §PRIORIDADE MÁXIMA; oráculo `scripts/harness/tests/test_faixas_aceite.py` |
| B2 | **Qualquer alteração exige pelo menos uma task — e nada além disso.** | ✅ (task avulsa) / 📄 (guard na árvore) | B1 + `ROADMAP-rodada-seguinte.md` §1 |
| B3 | **Hierarquia:** épico → sprint → feature(s) → tasks. Sprint dentro do épico; uma sprint tem VÁRIAS features; feature sempre dentro de sprint. Combinações válidas: A épico→sprint→feature→task · B sprint→feature→task · C sprint→task · D task avulsa. | 📄 | `ROADMAP-rodada-seguinte.md` §1, §3 |
| B4 | **Stories em duas formas, o harness escolhe:** simples (1 agente) = task tipada US/BUG/FIX; composta (>1 agente) = pasta `stories/<id>/` com tasks. | 📄 ⏳ tipo para manutenção técnica (sugestão `CHORE`) | `ROADMAP-rodada-seguinte.md` §1 |
| B5 | **Estado como árvore de pastas navegável** (um arquivo por item), em vez de tudo concentrado em JSON5. | 📄 | `ROADMAP-rodada-seguinte.md` §3–4, §7 |
| B6 | **`state/` só com o que executa agora**; `backlog/` (esperando) e `archive/` (fechado, mesma árvore; avulsas por ano/mês). | 📄 | `ROADMAP-rodada-seguinte.md` §2, §6 |
| B7 | **Comandos** `/new-epico`, `/new-feature`, `/new-sprint`, `/new-task` e `/close-task`, `/close-feature`, `/close-sprint`, `/close-epico` — e o harness também infere pela triagem. Tudo mecânico (economia de tokens). | 📄 | `ROADMAP-rodada-seguinte.md` §5–6 |
| B8 | **Uma feature ativa por vez** em `state/`; tasks da feature em paralelo quando não há colisão de arquivos. | 📄 | `ROADMAP-rodada-seguinte.md` §1 (ONE-FEATURE, PARALLEL-1) |
| B9 | **Salvar/carregar sessão cirúrgico:** carimbo com o que fechou, frente atual, tasks com resumo, em andamento, próximos passos com comando pronto, backlog, decisões humanas, integridade — zero dúvida para continuar. | 📄 | `ROADMAP-rodada-seguinte.md` §8 (SESSION-1..3) |
| B10 | **v8 como aprendizado, não molde** — é evolução; nossas decisões prevalecem. | 📄 | `ROADMAP-rodada-seguinte.md` §0 |
| B11 | **Modo autônomo fraco, sem máquina de estado** — precisa entregar uma frente sozinho, respeitando o harness. Pesquisa feita (web + skill orquestrar-subagentes). | 🧪 desenho pronto, aguarda aprovação | `docs/AUTONOMIA-DESENHO.md` (máquina M5 `mandato`, plano em DAG, escalada em níveis sem trancar, orçamento medido, 28 cenários AUTO-*) |

## C. Instalação, versão e higiene

| # | Ponto | Status | Onde |
|---|---|---|---|
| C1 | Comando acionável `/codebase-specialists [--full\|status\|retomar\|uso]` e guia de uso. | ✅ | `SKILL.md`, `MODO-DE-USO.md` (commits `80d27e1`, `e37cd00`) |
| C2 | **`upgrade`** com versão e manifesto de migrações: atualiza só harness/regras/artefatos, sem refazer entrevista/roster; repositório legado sem versão suportado. | 📄 | `ROADMAP-proxima-rodada.md` §P1 upgrade (UPGRADE-1..6) |
| C3 | **Renomear `.specialists/` → `.swarm/`.** | 📄 | `ROADMAP-proxima-rodada.md` §P1 rename (SWARM-DIR-1..4) |
| C4 | **Um harness só:** nunca coexiste com v8 (harness anterior) ou outro; substitui com backup, importando o conhecimento, só com `--replace-harness`. | 📄 | `ROADMAP-proxima-rodada.md` §P1 rename (SWARM-DIR-2, -4) |
| C5 | `--fast` como modo padrão; `--full` sob pedido. | ✅ | iteração 4 (commit `deefa36`) |

## D. Qualidade e método

| # | Ponto | Status | Onde |
|---|---|---|---|
| D1 | **A auto-correção tem de testar TODO o workflow** do harness (épico/sprint/feature/tasks, faixas, desvios, escalada, sessão, autonomia). | 📄 obrigatório em toda rodada | `ROADMAP-proxima-rodada.md` §OBRIGATÓRIO (vivacidade + WORKFLOW-E2E); lição L16 da `auto-correcao` |
| D6 | **Todo o harness testado E2E e comprovado 100% funcional** — principalmente a máquina de estado, o modo autônomo (atual e o novo), tudo. Critério mecânico: cobertura de 100% das transições de todas as máquinas e de cada guarda passando e recusando, medida pelos eventos das suítes; sem 100%, sem commit. O modo autônomo NOVO nasce com os 28 cenários AUTO-* e a mesma exigência. | 🔧 oráculo `test_cobertura_maquinas.py` em escrita (agente separado do corretor); E2E de 20 testes já congelado | `scripts/harness/tests/test_workflow_e2e.py`, `test_maquinas_vivacidade.py`, `test_cobertura_maquinas.py` |
| D2 | Cuidado com regressão — avaliar o que a máquina de estado atual pode e não pode perder. | ✅ checado nas 3 faixas (nenhuma máquina/transição/guarda/função removida; 480 testes) · 🔧 repetir após A1/A2 | — |
| D3 | Skill **`auto-correcao` global** (não vinculada à codebase-specialists) para corrigir qualquer sistema medindo. | ✅ v0.2 + docs; primeira campanha real em andamento (B1/A1) | `~/.claude/skills/auto-correcao`; lições L15/L16 novas |
| D4 | Documentação completa com diagramas, exemplos e cada fase — das duas skills. | ✅ | `docs/` das duas skills (commits `30435a4`, `5c9c724`) |
| D5 | Prompt pronto para a próxima rodada (não fizemos todas as rodadas por custo). | ✅ | `docs/ROADMAP-proxima-rodada.md` |

## E. Decisões de base (desde o início)
JSON5 em tudo que a máquina lê (não .md); memória por agente com autocorreção e teto de crescimento; execução em
etapas, uma janela por etapa; roteador de modelos (delegar ao mais barato); scripts mecânicos para salvar/carregar
sessão; máquinas de estado para delegação; Python + Makefile; conhecimento do próprio projeto (árvore territorial,
grafos de stack/dependência/colisão); processo com épico/sprint/feature/tasks (B3 é a forma corrigida); modo
autônomo (B11 é a reescrita). Todos implementados em alguma forma; os ajustes estão nas seções acima.

## Ordem combinada (revisada pelo founder em 2026-10-04)
1. Cobaia repositório-piloto: fechar campanha-iter8 (D-1-04), reinstalar o motor, 2º legacy-ack (founder), destravar KEY → OPS/AGT/QA.
2. `.swarm/` + harness único (`--replace-harness`, nunca ao lado do v8) — campanha própria.
3. **Estado em árvore (pastas)** logo em seguida — épico → sprint → feature(s) → tasks; backlog/state/archive;
   `/new-*` e `/close-*`; uma feature ativa; carimbo de sessão de 8 blocos. Absorve o que a cobaia revelou:
   `amend` de épico/feature, regularizar trabalho já existente (DoR de feature com teste vermelho), D-0-12.
4. Depois: medição real (execuções pausadas, sanitize em init completo, evals 4–6), comandos de pacotes de entrada,
   ajustes pequenos, modo autônomo novo (após aprovação do desenho), auto-correcao v0.3.
