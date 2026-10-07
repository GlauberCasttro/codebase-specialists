---
name: fechar-frente
description: >
  Encerra uma frente ativa de desenvolvimento da codebase-specialists: gate de aceite com completude cruzada (tasks,
  gates, aceites QA/Review, portão VERDE, conferir-commit, aprovação do founder na campanha), fecha a campanha no
  motor embutido (a conferência é do founder), consolida tudo no documento único
  .claude/state/archive/<frente>/<frente>.md, registra LAST_DELIVERY, limpa o estado transitório, volta a IDLE e
  commita SÓ os arquivos da frente num índice temporário (nunca alterações de terceiros, nunca push). Ritual
  idempotente e retomável. Use quando o founder disser "fecha a frente", "/fechar-frente", "encerra a iterN",
  "terminamos essa frente", "commita a frente", "volta pra IDLE", ou para retomar um fechamento interrompido.
disable-model-invocation: true
---

# /fechar-frente — encerrar uma frente ativa e voltar a IDLE

Fecha a frente `<id>` (uma das ativas em `.claude/state/frentes.json`), consolidando o trabalho num **documento
único** no `archive/` e tirando a frente de `ativas` — o que libera vaga para a próxima `/criar-frente`.

**Ritual idempotente:** cada passo é uma **pós-condição verificável no disco**, nunca "eu já rodei isso".
Reexecutar depois de uma interrupção retoma de onde parou, sem erro e sem efeito duplicado.

**Quem decide é o script:** `python3 .claude/tools/frente.py fechar <passo> <id>`. Cada passo confere a sua
pré-condição e recusa (exit 1, nada escrito) se faltar. A você cabe o julgamento: as notas do archive (Resumo,
Decisões técnicas, Aprendizados), a curadoria do BACKLOG, a mensagem do commit e o relatório ao founder.

```bash
python3 .claude/tools/frente.py fechar plano <id> --json     # archive|entrega|limpar|idle: feita? (pós-condição)
```

Comece sempre pelo `plano`: ele diz em que passo a frente está. Frente adotada como `legado` (sem tasks) não passa
por este ritual: feche a campanha pela `/auto-correcao` e combine com o founder.

---

## Contrato

### Artefatos

| Artefato | Caminho | Papel |
|---|---|---|
| Estado (verdade) | `.claude/state/frentes.json` | `ativas` → `entregues` no IDLE (só o script escreve) |
| Frente | `frentes/<id>/FRENTE.md` | CAs e os dois aceites |
| Tasks | `frentes/<id>/TASKS/*.md` | status/gate; `## Handoff` vai para o archive; removidas na limpeza |
| Índice / Ledger | `frentes/<id>/INDEX.md` · `HISTORICO.md` | contagem esperada · `## [PASS] <task>` |
| Criação | `frentes/<id>/CHECKLIST.md` · `eventos.jsonl` · `propostas/` | como a frente nasceu (5 aprovações); consumidos |
| Log | `.claude/state/logs/<id>/<id>.md` | histórico bruto; removido na limpeza |
| Campanha | `campanhas/<id>/` (+ `.auto-correcao/` local) | aprovação do founder, oráculo congelado, decisão |
| Portão | `local/portao-<id>/portao.out` + cópia testada | VERDE nos 2 Pythons; fonte da verdade do commit |
| **Archive** | `.claude/state/archive/<id>/<id>.md` | **documento único** — a memória permanente |
| Última entrega | `.claude/state/LAST_DELIVERY.md` | `**Frente-ID:** <id>` na primeira linha do corpo |
| Workflow | bloco gerado do `WORKFLOW.md` | IDLE (ou IN_PROGRESS com a outra ativa) + última entrega |

### Pode / Não pode

| ✅ Pode | ❌ Não pode |
|---|---|
| escrever **um** arquivo em `archive/<id>/` | qualquer outro arquivo nessa pasta (o hook nega; o `idle` recusa intruso) |
| remover `frentes/<id>/` e `logs/<id>/` **depois** do archive validado | remover qualquer coisa antes |
| levar ao projeto, por `portar.sh`, só o que o portão VERDE testou | editar produto à mão "para fechar" |
| commitar só os Arquivos da frente + oráculo + o estado desta frente | commitar arquivo de terceiros, mesmo em stage |
| avisar o founder do que só ele faz (senha, `frase conferir`) | rodar o script de aprovação, pedir a senha, aprovar pela IA, push |

### Definição de "archive completo"

`archive/<id>/<id>.md` existe e tem `## Resumo`, `## Critérios de aceite` (`### CA-NN` por CA), `## Linha do tempo`,
`## Tasks`, `## Como a frente nasceu` (os handoffs do CHECKLIST, com cada `Aprovação: "…"`), `## Campanha`,
`## Oráculo`, `## Decisões técnicas`, `## Aprendizados`, `## Arquivos da frente` (só os das tasks CORRECAO) e
`## Aceite da Frente` com `Aceite QA — ACCEPT` e `Aceite Review — APPROVED`; a **última linha**, gravada numa escrita
separada, é `<!-- fechar-frente:archive-completo -->`. Sem o marcador, o archive está incompleto e nada é removido.

---

## Passo 0 — Pré-requisitos que não são deste ritual

Antes do gate, a frente precisa ter passado pelo ciclo (é o `/tech-lead` que conduz):

- toda task `DONE` com `gate: PASS` marcada por `python3 .claude/tools/frente.py task marcar <id> <task> --status
  DONE --gate PASS` (o script exige o Handoff e apensa `## [PASS]` no HISTORICO);
- `### Aceite QA — ACCEPT` (QA pela régua completa do `/e2e-loop`) e `### Aceite Review — APPROVED` (`/revisor`
  isolado) no FRENTE.md, registrados pelo tech-lead;
- **portão VERDE** da frente sobre a lista exata dos Arquivos da frente, rodado em background:
  `bash .claude/tools/portao.sh <id> --lista local/<id>-arquivos.txt --oraculo campanhas/<id>/oraculo:<modulo>`
  até `FIM`, e `bash .claude/tools/portar.sh <id> …` levando a cópia testada ao projeto (merge de 3 vias; para em
  conflito; houve merge ⇒ rode o portão de novo com `--src .`);
- **aprovação do founder** na campanha (`gate stop`, `gate oracle:requisito`, `preauth commit`): ele roda
  `local/aprovar-<id>.sh` no terminal dele, com a senha.

## Passo 1 — Gate de aceite + completude cruzada (bloqueante, NUNCA escreve)

```bash
python3 .claude/tools/frente.py fechar check <id> --json
```

Reprovou ⇒ **nada é escrito**, a frente continua ativa e o script lista o que faltou, por código:

| Código | O que conferiu | Por quê |
|---|---|---|
| `completude_divergente` | `N_index == N_disco == N_done` (> 0) e os mesmos ids no INDEX e em `TASKS/` | "nenhuma task aberta" e "nenhuma task existente" são indistinguíveis numa pasta — a contagem cruzada separa os dois |
| `task_aberta:<id>` | toda task DONE | |
| `gate_ausente:<id>` | `gate: PASS` no cabeçalho **e** `## [PASS] <task>` no HISTORICO | o gate tem de ter sido registrado pelo script, não só escrito no cabeçalho |
| `aceite_ausente:qa\|review` | `### Aceite QA — ACCEPT` e `### Aceite Review — APPROVED` | quem aceita é o founder, com base nos dois pareceres |
| `portao_nao_verde` | `local/portao-<id>/portao.out` termina em `RESULTADO: VERDE` + `FIM` | |
| `conferir_commit` | `conferir-commit.sh <id> -- <Arquivos da frente>`: vivo byte a byte = cópia testada | só entra no commit o que o portão testou |
| `campanha_sem_aprovacao` | `ac.py check intake.3` (gate stop do founder) | sem a senha do founder não há fechamento |
| `oraculo_nao_intacto` | `ac.py oracle verify` | oráculo mudado fora de `oracle change` invalida a medida |

Faltou a aprovação ⇒ diga ao founder: "rode `sh local/aprovar-<id>.sh` no seu terminal". Nunca contorne.

## Passo 2 — Fechar a campanha no motor (sequência do método)

```bash
python3 .claude/tools/campanha.py fechar <id> --relatorio <relatorio.md> --config sistema --decisao GO --dry-run
python3 .claude/tools/campanha.py fechar <id> --relatorio <relatorio.md> --config sistema --decisao GO
```

O script roda, em ordem: `front report` → `done correcao` → `set integration.tests_green true` → `done integracao` →
`run record` (espera 1 s: AC-09) → `done remedicao` → `set decision`/`set report`, e **para** na linha do founder:

    FOUNDER (no terminal dele): python3 .claude/tools/ac/ac.py --work campanhas/<id> frase conferir

Avise e pare; você não roda. Depois da conferência: `campanha.py fechar <id> … --concluir` (roda `done decisao`).
O motor recusa (ex.: "etapa 'base' não fechou") ⇒ o script para com a mensagem do motor; resolva a etapa da campanha
(é do ciclo da `/auto-correcao`, não do fechamento) e retome.

## Passo 3 — Consolidar no documento único

Escreva as notas (julgamento; fora do estado, ex. `local/fechar-<id>/notas.md`) com `## Resumo`,
`## Decisões técnicas` e `## Aprendizados` (inclusive os erros e o que custou ciclo). Depois:

```bash
python3 .claude/tools/frente.py fechar archive <id> --notas local/fechar-<id>/notas.md
```

Exige o gate do Passo 1 verde (reprovado ⇒ nada escrito). O script monta o archive a partir das fontes, nesta ordem
de custo: FRENTE (CAs e aceites), eventos e HISTORICO (linha do tempo), **só** o `## Handoff` de cada task (nunca a
task inteira), CHECKLIST (como nasceu, com as aprovações literais), estado da campanha e oráculo, suas notas; e
`## Arquivos da frente` = os Arquivos permitidos das tasks CORRECAO — a **única** fonte do commit. Grava o marcador
em escrita separada e valida. Archive já completo ⇒ 0 sem escrever (idempotente). Arquivo intruso na pasta ⇒ recusa
(nunca apaga).

## Passo 4 — Registrar a entrega

```bash
python3 .claude/tools/frente.py fechar entrega <id>      # LAST_DELIVERY.md: "**Frente-ID:** <id>" + data, archive, HEAD
```

## Passo 5 — Backlog (julgamento)

Curadoria é sua: tire o item entregue ("em frente <id>"), ajuste o que foi resolvido parcialmente (não remova),
promova a próxima a P0. Não deduza sozinho que outros itens foram atendidos.

## Passo 6 — Limpar o estado transitório

```bash
python3 .claude/tools/frente.py fechar limpar <id>       # remove frentes/<id>/ e logs/<id>/ — só com archive completo
```

Pré-condição rígida: archive completo. **Nada é apagado antes de o substituto estar validado.**

## Passo 7 — Transição para IDLE

```bash
python3 .claude/tools/frente.py fechar idle <id>
```

Confere contra o disco: archive completo **e único**, limpeza feita, LAST_DELIVERY com o id. Qualquer falta ⇒ não
transiciona (exit 1, diz o quê). Passou: tira a frente de `ativas`, põe em `entregues` e regrava o bloco do WORKFLOW
(IDLE se não sobrou ativa). Reexecutar não muda nada.

## Passo 8 — Commit só da frente

```bash
python3 .claude/tools/frente.py fechar commit <id> --mensagem local/fechar-<id>/msg.txt [--decisions ARQ] --dry-run --json
python3 .claude/tools/frente.py fechar commit <id> --mensagem local/fechar-<id>/msg.txt [--decisions ARQ]
```

| Entra | Fica fora (reportar como intacto) |
|---|---|
| cada caminho de `## Arquivos da frente` | qualquer caminho fora da lista, **mesmo em stage** |
| `campanhas/<id>/oraculo/` e `campanhas/README.md` | outras campanhas |
| do estado: `archive/<id>/`, `frentes/<id>/`, `logs/<id>/`, `LAST_DELIVERY.md`, `WORKFLOW.md`, `frentes.json`, `RESUME.md`, `BACKLOG.md` — os que mudaram | skills, tools e demais arquivos que a frente não declarou |
| `DECISIONS.md` **só** por `--decisions ARQ` | linhas de DECISIONS de outra sessão |

O script exige a **pré-autorização** do founder (`ac.py check integracao.3` — o `preauth commit` do script de
aprovação), roda `conferir-commit.sh` e o **guard de privacidade** nos caminhos e na mensagem, e commita num
**índice temporário** a partir do HEAD — o stage de terceiros fica em stage e fora do commit; o índice real só é
realinhado nos caminhos commitados. **DECISIONS.md:** confira `git diff -- .claude/state/DECISIONS.md`; todas as
linhas novas são da frente ⇒ `--decisions .claude/state/DECISIONS.md`; há linha alheia ⇒ gere uma cópia em `local/`
sem ela e passe essa; sem como separar ⇒ não passe e reporte como pendente. Recusou (privacidade, conferir, sem
pré-autorização) ⇒ **não contorne**; o fechamento já está válido em IDLE; reporte. **Nunca** push, reset,
checkout --, stash, clean.

Depois do commit, é julgamento seu: `campanhas/README.md` (commit de entrega e decisão), `RESUME.md`; depois
`/install` (a skill instalada nesta máquina passa a ser o pacote do HEAD novo) e `/salvar-sessao` (commit só do
estado).

## Passo 9 — Sinalizar

    Frente {id} encerrada. Estado: {IDLE | IN_PROGRESS (outra ativa: …)}
    Archive: .claude/state/archive/{id}/{id}.md
    Campanha: campanhas/{id}/ — decisão {GO} (conferência do founder: {feita | pendente})
    Commit da frente: {sha} · fora do commit: {— | caminhos de terceiros, intactos}
    Git: {branch} @ {HEAD} · push: não (só o founder) · próximo: /install, depois o topo do BACKLOG

---

## Invariantes

1. Nenhuma escrita antes do gate do Passo 1 passar.
2. **Nada é apagado antes de o substituto estar validado** — limpeza só com archive completo.
3. Todo passo é pós-condição verificável; reexecutar é seguro (idempotente).
4. `archive/<id>/` contém exatamente um arquivo.
5. IDLE só depois de archive completo e único, limpeza e LAST_DELIVERY.
6. O commit contém só a frente; push nunca. Senha, `frase conferir` e o script de aprovação são do founder.

## Ponteiros

- Controlador: `.claude/tools/frente.py fechar …` · campanha: `.claude/tools/campanha.py fechar`
- Portão e entrega: `.claude/tools/portao.sh`, `.claude/tools/portar.sh`, `.claude/tools/conferir-commit.sh`,
  `.claude/tools/guard-privacidade.sh`
- Par: `/criar-frente` · execução: `/tech-lead` · régua: `/e2e-loop` · sessão: `/salvar-sessao` · depois: `/install`
