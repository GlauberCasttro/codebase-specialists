# 08 — Limites e defeitos conhecidos

Este documento diz o que a skill **não** garante, o que está quebrado hoje e quanto ela custa. Fontes:
`references/harness.md` §9, `references/platforms.md` §5, `references/probes.md` §11, `evals/README.md`,
o registro de resultados e defeitos da iteração 4 (interno), notas das execuções e o próprio código.

## 1. O que não é garantido

### Enforcement

- **Só o Claude Code bloqueia antes.** Cursor, Copilot e Codex recebem instrução + estado por CLI (E1) e
  detecção depois do fato (E2: `cs-state verify`, `cs-precommit`/CI). Nada impede a escrita fora do território
  até o commit/verify. O relatório mostra isso por plataforma (`enforcement: hook|instructions`).
- **Mesmo no Claude Code, programa arbitrário escreve.** `python foo.py`, `npm …` podem escrever onde quiserem: o
  parser do guard de Bash não vê o que um programa faz (E2, não E3). O `verify` pega depois.
- **Comandos legítimos com `$(…)`, crase ou heredoc são bloqueados por desenho** — use script em arquivo.
- **Cadeia de hashes sem segredo**: detecta edição ingênua de `events.jsonl`/ledgers; quem reescreve a cadeia
  inteira por script (fora dos guards) não é detectado — mitigado por guard de Bash + verify, não eliminado.
- **Um agente com 2 delegações em voo é bloqueado** (o ator é identificado por `agent_type`; 1 em voo por
  agente).
- **A confirmação da classe `risco` grava a frase informada pelo orquestrador**; o motor não prova que o usuário
  disse aquilo.
- Lock por `fcntl` (no Windows não há lock entre processos). BSD make não testado (o `/usr/bin/make` do macOS é
  GNU 3.81).

### Medição

- **G9, G10, G11, G12, G14 e G15 medem o motor da skill**, pelas suítes de teste da própria skill — não uma
  execução no seu repositório. **G11 é parcial**: o eval end-to-end de autonomia não roda no `verify`.
- **G3 é léxico** e foi calibrado com cartões genéricos de referência, não com um repositório de controle.
- **Modo `--fast` não certifica o time**: o relatório diz "time NÃO certificado como especialista".
- **Exame isolado não é estanque**: com `--out` dentro de `.swarm/tmp/`, o banco de sondas fica alcançável
  por `../../..`; a instrução do exame proíbe sair da cópia, mas não há bloqueio mecânico. Para certificação
  estrita, use `--out` fora do alvo (`references/probes.md` §11).
- **Modo fechado não é placar**: é sinal (cartão = mapa).
- **Território sem sonda discriminante é "não medido"** (`baseline_saturated: true`), não reprovado — e também
  não aprovado com o mesmo rigor.
- **99% exige volume**: afirmar ≥99% de precisão com 95% de confiança exige ~300 aceites consecutivos sem falso
  aceite (premissa PR-17). Nenhuma rodada chegou perto disso.

### Plataformas (`references/platforms.md` §5)

- O Cursor lê `.claude/agents/` e `.codex/agents/` além de `.cursor/agents/`: emitindo as três, o mesmo agente
  aparece em mais de um diretório (a doc do Cursor não define precedência).
- `AGENTS.md` aninhado é lido por Codex, Copilot e Cursor: com várias plataformas, o S2 de um território chega a
  esses agentes por dois caminhos.
- Formatos de plataforma confirmados na documentação oficial em 2026-10-01; se a doc mudar, o validador do G7
  (`scripts/emit/validate.py`) precisa mudar junto.

## 2. Defeitos abertos (iteração 4)

De registro interno de defeitos da iteração 4 (`defeitos_iter5`), conferidos contra o código atual:

| Prio | Defeito | Estado no código hoje | Efeito prático |
|---|---|---|---|
| P0 | `--fast` pula rt.2/rt.4, a única checagem de existência antes do `verify` → G2 falha no verify. Proposta: rodar `probes existence` em specialize.4 (ou validate.1) em todos os modos e permitir `team card revise` sem painel consolidado para consertar existência | aberto: `scripts/team/cards.py → card_revise` levanta "painel de <a> não consolidado" quando não há `panel/<a>.json5` | no `--fast`, primeiro `verify` tende a NO-GO por G2 (ts-shop iter. 4: 0,9723; py-billing iter. 3: 0,9803) e não há caminho documentado de conserto |
| P0 | `verify` aceita G4 com cartões alterados depois do exame (exame deveria ficar ligado ao hash do cartão) | aberto: o `inputs` do acceptance cobre team/bank/manifest/fatos/harness, mas o placar de sondas não é invalidado por mudança de cartão | GO possível sobre cartões que não foram examinados (ts-shop iter. 4) |
| P1 | sem comando que monte os pacotes de entrada de spot-check, core e juízes POR-QUÊ (`facts spotcheck pack`, `team core pack`, `panel why pack`) nem a maioria dos juízes (`panel why tally`) | aberto: `facts spotcheck` só tem `--min` e `record`; `team core` só `set`/`from-panel`; `panel why` só registra um veredito | o orquestrador escreve scripts para montar entradas e agregar juízes (contornos manuais 1–4 da ts-shop iter. 4) |
| P1 | `probes exam-pack` grava `answer_file` em conflito com o caminho de respostas de `prompts.json5` | aberto: `scripts/probes/exam.py` grava `answer_file = <out>/answers.json5`; `references/stages.json5` (validate.3) também cita `<out>/answers.json5`; `references/prompts.json5` e `references/probes.md` mandam `{tmp}/answers/<a>.guided\|closed.json5` | duas fontes oficiais divergem; o executor precisa escolher (iteração 4 seguiu `prompts.json5`) |
| P2 | corretor [Q][STALE] não reconhece negação ("não existe", "não documentar como existente") | aberto (corretor) | falso negativo de qualidade (ts-shop iter. 4: 12/13 no corretor, 13/13 real) |

Contornos manuais da única execução concluída da iteração 4 (ts-shop, `outputs/notes.md`):

1. pacote de entrada do spot-check montado por script;
2. `{tmp}/in/core.json5` escrito à mão;
3. itens dos juízes POR-QUÊ montados por script a partir do bank;
4. script de maioria dos juízes chamando `panel why` e `probes check`;
5. conserto de existência (G2) depois do verify: prompt próprio, 7 subagentes, `team card set` no lugar do
   `team card revise` (que recusou), reemissão e novo verify — com os exames pontuados sobre os cartões antigos.

Critério de parada da campanha (≥2/3 GO; zero contornos manuais; [Q] ≥ baseline nos 3; testes verdes):
**não cumprido** (`criterio_parada.veredito: "NÃO CUMPRIDO — 5 contornos manuais"`). As execuções de py-billing
(validate.3) e go-polyglot (validate.2) ficaram pausadas; a retomada fica para a próxima
rodada.

## 3. Divergências documentação × código encontradas

Além do P1 acima (caminho de respostas), ao escrever esta documentação:

- `references/team-schema.md` diz que o conserto de existência por `team card revise --file` "é aceito a
  qualquer momento"; o código só aceita com painel consolidado (ver P0).
- `references/platforms.md` §4.1 diz que `--no-settings` desliga `.claude/settings.json` **e**
  `.claude/hooks/cs-guard.sh`; o código (`scripts/harness/install.py → write_bins`) escreve o wrapper mesmo com
  `--no-settings`.
- O `--help` tem lacunas (`interview sync`, `panel pack`, `harness validate|status`, subcomandos de `cs-route`
  sem descrição; `harness install --platforms` sugere só `cursor,copilot,codex`) — lista em
  [06-referencia-cli.md](06-referencia-cli.md).
- `references/ARCHITECTURE.md` §5 intitula "Camadas do scan (L0–L8)" e a tabela de §9 lista só G1–G7; L9/L10 e
  G8–G16 estão descritos nas seções §8-bis…§8-terdecies.

## 4. Custo medido

Números das rodadas (tokens = só o orquestrador; subagentes **não** contabilizados — as notas de `timing.json`
dizem que o custo real é "bem maior"):

| Execução | Tempo | Tokens do orquestrador | Subagentes |
|---|---|---|---|
| Baseline sem skill (média iteração 2) | 425 s (~7 min) | 90.036 | — |
| Com skill, completo (média iteração 2) | 2.938 s (~49 min) | 357.836 | não contados (~40+ na py-billing) |
| py-billing `--fast` (iteração 3) | 1.402 s (~21–23 min) | 230.405 | 33 (lotes ≤3, nenhum 429) |
| ts-shop `--fast` (iteração 4) | 1.975 s (~33 min) | 269.008 | 79 (2 spot-check + 10 redatores + 10 baseline + 10 guiados + 10 fechados + 30 juízes + 7 consertos) |

O `MODO-DE-USO.md` estima ~20–30 min num repositório pequeno/médio no `--fast` e ~2× no `--full`. O maior item
de custo no `--fast` é o painel de juízes POR-QUÊ (3 por agente) e o exame em dois modos.

## 5. Quando algo der errado

Anote o comando exato e o erro literal, e qualquer contorno que você precisou fazer (MODO-DE-USO.md). Esse
registro alimenta a skill `auto-correcao` na próxima rodada de melhoria. Nas execuções de avaliação, isso vai em
`outputs/notes.md` sob "CONTORNOS MANUAIS".
