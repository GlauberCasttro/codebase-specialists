# iter22 — cs-state show liberado no guard do alvo, varredura que impede subcomando sem regra no guard, versão 0.12.1

## Resumo
Hotfix 0.12.1: o `cs-state show` (entregue na 0.11.0) estava inacessível nos alvos porque o cs-guard o barrava como
"subcomando desconhecido" (`show` fora de STATE_SUB). Agora o show passa pelo hook para o agente principal e, por ser
só leitura, para o subagente; e uma varredura de teste compara cada subcomando do argparse do cs-state com as regras
do guard e reprova o subcomando novo sem regra. Docstring do caderno atualizada. 0.12.1 no catálogo (ação harness).

## Critérios de aceite
### CA-01 — show liberado para o agente principal
DADO um alvo com o harness instalado (hook pre-bash ativo) e uma
  task existente, QUANDO o agente principal roda `.swarm/bin/cs-state show <id>` pelo hook pre-bash, ENTÃO o guard
  libera (exit 0, sem "desconhecido") e o comando imprime a task em Markdown.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA01`

### CA-02 — show liberado para subagente (leitura)
DADO o mesmo alvo e um subagente em delegação, QUANDO ele roda
  `cs-state show <id>` pelo hook pre-bash, ENTÃO o guard libera como as demais leituras (board, next, find…), e um
  subcomando que muda estado continua barrado para o subagente.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA02`

### CA-03 — nenhum subcomando sem regra no guard
DADO o argparse do `state.py`, QUANDO se compara cada
  subcomando de nível superior com o guard, ENTÃO todo subcomando tem entrada em STATE_SUB ou regra explícita no
  guard; e um subcomando fictício acrescentado ao argparse sem entrada faz o teste FALHAR.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA03`

### CA-04 — versão 0.12.1 leva a correção aos alvos
DADO um alvo 0.12.0, QUANDO roda `cs.py upgrade` e
  `upgrade --apply --allow-outside`, ENTÃO o plano lista a migração 0.12.1 (harness), o apply reinstala o guard e
  o `cs-state show` passa pelo hook; VERSION é 0.12.1 com a migração no catálogo; a docstring do caderno descreve o
  comportamento atual; os oráculos iter16/18/19/20/21 seguem inteiros verdes.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA04`

## Linha do tempo
- 2026-10-12T14:45:18-0300 · inicio E0
- 2026-10-12T14:45:30-0300 · proposta E1
- 2026-10-12T14:49:14-0300 · aprovacao E1
- 2026-10-12T14:49:57-0300 · proposta E2
- 2026-10-12T14:50:16-0300 · aprovacao E2
- 2026-10-12T14:50:46-0300 · proposta E3
- 2026-10-12T14:51:08-0300 · aprovacao E3
- 2026-10-12T14:51:39-0300 · proposta E4
- 2026-10-12T14:52:09-0300 · aprovacao E4
- 2026-10-12T14:52:09-0300 · proposta E5
- 2026-10-12T14:54:10-0300 · aprovacao E5
- 2026-10-12T14:54:10-0300 · abertura abertura
- [NOTA] 2026-10-12T14:54:10-0300 — Abertura da feature iter22
- [NOTA] 01-TASK-ORACULO — 2026-10-12T14:54:20-0300
- [PASS] 01-TASK-ORACULO — 2026-10-12T14:59:42-0300
- [NOTA] 02-TASK-GUARD-SHOW — 2026-10-12T15:12:19-0300
- [NOTA] 03-TASK-VERSAO — 2026-10-12T15:12:19-0300
- [PASS] 02-TASK-GUARD-SHOW — 2026-10-12T16:12:11-0300
- [PASS] 03-TASK-VERSAO — 2026-10-12T16:12:11-0300
- [NOTA] 04-TASK-QA — 2026-10-12T16:12:17-0300
- [PASS] 04-TASK-QA — 2026-10-12T16:53:54-0300
- [NOTA] 05-TASK-REVIEW — 2026-10-12T16:53:54-0300
- [PASS] 05-TASK-REVIEW — 2026-10-12T16:55:29-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter22 (CA-01..CA-04), escrito por agente separado | ORACULO | — | DONE | PASS |
| 02-TASK-GUARD-SHOW | show em STATE_SUB, varredura subcomandos × guard e docstring do caderno | CORRECAO | G1 | DONE | PASS |
| 03-TASK-VERSAO | 0.12.1 com migração no catálogo e nota de upgrade | CORRECAO | G2 | DONE | PASS |
| 04-TASK-QA | Portão e oráculos, CA a CA | QA | — | DONE | PASS |
| 05-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus), agente separado (não leu local/work).
- Entregue: ESPEC.md, test_iter22.py (9 testes: 6 D, 3 R; show exercitado PELO hook pre-bash instalado no alvo),
  medir.py, base.txt. CA-04 monta o alvo 0.12.0 por `git archive 7fdb431` (ou $CS_OLD_SKILL_DIR).
- Medido pelo tech-lead no HEAD d2e07ff: 3/9 (D 0/6, R 3/3), idêntico em python3 3.13 e /usr/bin/python3 3.9; motivo
  de cada D: "cs-state show desconhecido", "subagente não roda cs-state show", ['show'] != [], VERSION 0.12.0 < 0.12.1,
  plano "nada a fazer", docstring antiga.
- Calibração (oraculista, cópias em mktemp): correção mínima ⇒ 9/9 nos 2 Pythons; mutação CA-03 (subparser fictício
  sem regra) ⇒ FAIL. Congelado: `oracle freeze` 524416ebaf44 (4 arquivos); oracle verify intacto.
- Lacunas declaradas: CA-02 sem delegação em voo (o guard decide pelo subcomando); docstring testada por heurística de
  texto; CA-03 detecta "sem regra" pela palavra "desconhecido".

### Handoff 02-TASK-GUARD-SHOW
- Executor: general-purpose · sonnet (ciclo 1). RED não observado pelo executor; o RED é a base do oráculo no HEAD
  (3/9: "cs-state show desconhecido", "subagente não roda cs-state show", ['show'] != [], docstring antiga).
- Arquivos: scripts/harness/engine/guard.py (`show` em STATE_SUB main e any; docstring de notebook_text_problems com o
  comportamento atual), scripts/harness/tests/test_iter22_guard.py (3: show pelo hook principal e subagente com
  mutação barrada; varredura argparse × STATE_SUB ∪ regras explícitas). Nenhum def removido.
- Tech-lead (cópia, 2 Pythons): oráculo iter22 9/9; régua completa VERDE (32/32; harness 372/16 skip, emit 63);
  escopo = arquivos permitidos; projeto vivo intacto; privacidade 0.
- Revisor: general-purpose · opus, instância isolada · APPROVED, sem findings (REVIEWS/02-03-revisao-pontual.md);
  mutação `zzfake` no argparse ⇒ varredura FAILED. MENOR: o conjunto EXPLICIT do teste é mantido à mão.

### Handoff 03-TASK-VERSAO
- Executor ciclo 1: general-purpose · sonnet — VERSION 0.12.1, README, catálogo (version 0.12.1; entrada to 0.12.1
  {kind: harness}), docs/09 "Migração 0.12.1". RED não capturado (editou antes); TestCA04 OK nos 2 Pythons.
- Régua do tech-lead reprovou: scripts/emit/tests/test_iter21_emit.py:109 fixava VERSION == "0.12.0" (classe B-32 numa
  suíte). Founder aprovou incluir o arquivo (escopo da campanha, task e FEATURE.md ajustados).
- Executor ciclo 2: general-purpose · opus — `assertGreaterEqual` por tupla (≥ 0.12.0), entrada `to: "0.12.0"`
  mantida e o cabeçalho do catálogo == VERSION (2ª asserção fixa encontrada e tratada). Mutações em mktemp: VERSION
  0.11.0 ⇒ FAIL; entrada 0.12.0 trocada ⇒ FAIL.
- Tech-lead (cópia, 2 Pythons): oráculo iter22 9/9; régua completa VERDE (32/32; emit 63); escopo conferido;
  privacidade 0. Revisor (opus, isolado) APPROVED a versão/catálogo (REVIEWS/02-03-revisao-pontual.md).

### Handoff 04-TASK-QA
- Portão rodado pelo tech-lead (lista local/iter22-arquivos.txt, 7 arquivos = Arquivos permitidos das CORRECAO;
  oráculos iter22, iter16, iter18, iter19, iter20, iter21 inteiros): VERDE + FIM nos 2 Pythons; oracle verify
  intacto. Matriz no Aceite QA do FEATURE.md. Declarado: não é QA independente.

### Handoff 05-TASK-REVIEW
- Revisor: general-purpose · opus, instância isolada que nunca executou nada na feature · APPROVED, sem findings
  (parecer em REVIEWS/05-revisao-feature.md); snapshot pré/pós sem mudança; custo registrado.
- Mutações em mktemp: subparser novo "zap" ⇒ varredura FAILED; "show" removido de STATE_SUB["any"] ⇒ FAILED.
- Limite: o teste do emit avaliado por inspeção (o executor do ciclo 2 já o provou por mutação).

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-12T14:45:18-0300
- Demanda: "B-35: corrigir já o bloqueio do cs-state show pelo guard, como versão 0.12.1 rápida"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-12T14:49:14-0300
- Produzido: problema enunciado; FEATURE-ID iter22
- Itens aprovados: 1: varredura subcomandos×guard: sim; 2: 0.12.1 com migração no catálogo: sim
- Aprovação: "ok"
- Sha: 2c548f2729199c628c916023dff9588e69a4933391579c23ae33bc3c3d570bc8
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-12T14:50:16-0300
- Produzido: investigação medida F1–F6
- Medido: 48 subcomandos; 42 no guard + 5 com regra explícita + 1 sem nada (show); 0 testes passam o show pelo hook
- Aprovação: "ok"
- Sha: 868e92ed9cca34d3834d70feec902d105c57509cfd974f4639f6ebe820bdd458
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-12T14:51:08-0300
- Produzido: FEATURE.md (4 CAs, contrato PASS)
- Aprovação: "ok"
- Sha: 8eeadeec59f384f34794257f2f010615c2697224700609cc27ac8c572689a77b
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-12T14:52:09-0300
- Produzido: 5 tasks (ORACULO, 2 CORRECAO G1/G2, QA, REVIEW)
- Aprovação: "ok."
- Sha: 9fad8c883c1908ce15e88cf2eba5a52e7a0eec546266132c20e74bc8539191f9
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-12T14:54:10-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: a51dbe136c89654cb5d566c673236802df5af8353d96e6badf2454a13a3f7f65
- Próxima: oráculo por agente separado

### Abertura · 2026-10-12T14:54:10-0300
- Campanha: campanhas/iter22
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/iter22 · etapa do motor: concluida · rodada: 0
- critério de parada: Oráculo iter22 100% verde (CA-01..CA-04) em python3 e /usr/bin/python3; oráculos iter16, iter18, iter19, iter20 e iter21 inteiros verdes; suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.12.1.
- escopo: scripts/harness/engine/guard.py, scripts/harness/tests/test_iter22_*.py, references/migrations.json5, docs/09-upgrade.md, VERSION, README.md, scripts/emit/tests/test_iter21_emit.py

## Oráculo
- `campanhas/iter22/oraculo/ESPEC.md`
- `campanhas/iter22/oraculo/test_iter22.py`
- `campanhas/iter22/oraculo/medir.py`
- `campanhas/iter22/oraculo/base.txt`

## Decisões técnicas
- `show` em STATE_SUB["main"] e ["any"]; fail-closed do desconhecido mantido; nenhuma outra lista mudou.
- Varredura lê as escolhas do `state.py --help` e exige main ∪ any ∪ regras explícitas (legacy-ack, waive-verify,
  dispatch, submit, review, abstain).
- Mudança de plano aprovada pelo founder: `scripts/emit/tests/test_iter21_emit.py` deixou de fixar a versão (B-32 numa
  suíte) — ≥ 0.12.0, entrada 0.12.0 no catálogo e cabeçalho == VERSION.

## Aprendizados
- A regressão do show escapou porque o teste chamava o cs-state direto, sem o hook. Toda funcionalidade de linha de
  comando do alvo precisa de teste pelo caminho real (o hook), não só pela função.
- Versão fixa aparece também em suítes (não só oráculos): a revisão da iter21 deixou passar. Regra: teste nunca fixa
  VERSION.
- O uso real na cobaia é o melhor detector: o defeito apareceu no primeiro uso do show depois do upgrade.

## Arquivos da feature
- `scripts/harness/engine/guard.py`
- `scripts/harness/tests/test_iter22_guard.py`
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `scripts/emit/tests/test_iter21_emit.py`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED

## Pareceres dos revisores (transcrição integral)

### Parecer — 02-TASK-GUARD-SHOW e 03-TASK-VERSAO (revisão pontual, tentativa 1)

Registrado pelo tech-lead em 2026-10-12. Snapshot pré/pós-revisor da cópia: nenhum arquivo mudou. Medição do
tech-lead: oráculo iter22 9/9 nos 2 Pythons (base no HEAD 3/9 = o RED); escopo = os 6 arquivos permitidos; projeto
vivo intacto; nenhum def removido; privacidade 0.

```
REVISOR: Claude Code · general-purpose · model: opus (passado pelo tech-lead) · instância isolada
BASE: HEAD f042083 + cópia local/work/iter22/codebase-specialists · arquivos examinados: 8

MATRIZ:
CA-01 → test_principal_show_liberado: hook pre-bash real, exit 0 sem "desconhecido"; state.py:283 declara o show
        "SÓ LEITURA: Markdown do item" → PASS
CA-02 → test_subagente_show_liberado_e_mutacao_barrada: show exit 0; close/start/new exit 2 (guard.py:332) → PASS
CA-03 → TestVarreduraArgparse: escolhas do `state.py --help` ⊆ main ∪ any ∪ EXPLICIT → PASS
CA-04 → VERSION 0.12.1; catálogo version 0.12.1 + to "0.12.1" {kind: harness}; docstring atual; upgrade medido pelo
        oráculo (9/9 do tech-lead) → PASS
F1 fail-closed: só "show" acrescentado (main e any); desconhecido segue recusado (guard.py:331); show só aceita `id`
   posicional, sem flag que escreva → PASS
F2 varredura: mutação em mktemp (`sub.add_parser("zzfake")`) ⇒ 3 OK → 1 FAILED; lê só o --help, sem board → PASS
F3 catálogo: formato igual à 0.12.0; "harness" em KINDS (version.py:26); why verdadeiro; docs/09 coerente → PASS
F4 docstring: descreve o corpo (só bloco == render; selo ok + bloco diferente ⇒ "desatualizado ou forjado";
   CRLF/BOM normalizados; sem mem ⇒ fail-closed) → PASS
test_iter22_guard.py: 3 OK em python3 e /usr/bin/python3.

FINDINGS: —
VEREDITO: APPROVED
LIMITES: não rodou o oráculo nem o upgrade real (depende do 9/9 medido pelo tech-lead).
LACUNAS: o conjunto EXPLICIT do teste é mantido à mão — se um subcomando novo entrar nele por engano, a varredura
não percebe (MENOR).
```

### Parecer — 05-TASK-REVIEW (modo feature, tentativa 1)

Registrado pelo tech-lead em 2026-10-12. Snapshot pré/pós-revisor: nenhum arquivo mudou.

```
REVISOR: Claude Code · general-purpose · model: opus (passado pelo tech-lead) · instância isolada · modo feature
BASE: f042083 + cópia · arquivos examinados: 11 (os 7 da lista + state.py, tree.py:show_md, version.py, portao.out)

MATRIZ:
CA-01 → guard.py:265 "show" em STATE_SUB["main"]; test_principal_show_liberado OK; oráculo 9/9 no portão → PASS
CA-02 → "show" em STATE_SUB["any"]; close/start/new pelo subagente ⇒ exit 2 → PASS
CA-03 → varredura argparse × guard passa; mutações a fazem falhar → PASS
CA-04 → VERSION, cabeçalho e to "0.12.1" {kind: harness}; README e docs/09 coerentes; CA04 OK no portão → PASS
Foco 1 → state.py:283 show só com `id`; state.py:362 → tree.show_md(tree.load_view(...)) só leitura (tree.py:1309);
         fail-closed: guard.py:331 (principal "desconhecido"), :346 (subagente); só mudou a docstring além do show → PASS
Foco 2 → mktemp: subparser "zap" ⇒ FAILED (failures=1); "show" fora do any ⇒ FAILED (failures=2) → PASS
Foco 3 → emit: ≥ (0,12,0), mantém to "0.12.0", cabeçalho == VERSION; não "sempre passa" → PASS
Foco 4 → kind harness em scripts/upgrade/version.py:26; README 0.12.1; docs/09 descreve o código → PASS
Execução nos 2 Pythons: test_iter22_guard OK (3); emit OK. Portão VERDE + FIM; oráculos iter16..iter22 OK.

FINDINGS: —
VEREDITO: APPROVED
LIMITES: não reexecutou o portão (leu portao.out); show_md conferido por grep de escrita; teste do emit por inspeção.
LACUNAS: —
```

<!-- fechar-feature:archive-completo -->
