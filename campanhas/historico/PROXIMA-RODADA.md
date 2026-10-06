# Prompt pronto — próxima rodada de testes da codebase-specialists

Cole o bloco abaixo numa sessão NOVA do Claude Code (de preferência logo após o reset do limite de uso).
Ele é autocontido: a sessão nova não precisa do histórico desta.

---

```
/auto-correcao

Campanha: refinar a skill codebase-specialists até o critério de parada abaixo. É a primeira campanha real da
auto-correcao — siga o ciclo dela (ac.py) à risca e registre tudo, inclusive onde a própria auto-correcao atrapalhar.

## Alvo e contexto (não refaça o diagnóstico; leia)
- Skill-alvo: ~/.claude/skills/codebase-specialists (repo git: ~/.claude/skills, remoto privado
  o repositório privado de skills, branch master; versione SÓ a pasta codebase-specialists/).
- Histórico das rodadas: campanhas/
  - iteration-3/RESULTADOS.json5 e iteration-3/PLANO-ITER4.json5 (decisões já tomadas: --fast é o padrão;
    GO exige todos especialistas; rascunhos em .specialists/tmp/; lotes ≤3 em primeiro plano)
  - iteration-4/RESULTADOS-E-DEFEITOS.json5  ← defeitos abertos (2× P0, 2× P1, 1× P2)
  - iteration-*/<eval>/with_skill*/outputs/notes.md (erros exatos de cada execução)
- Campanha da auto-correcao: campanhas/iter5 (use como --work).

## PRIORIDADE MÁXIMA (P0 da rodada 1) — interagir com os especialistas sem o fluxo inteiro
Problema (confirmado no código): para chamar QUALQUER especialista, o guard (`scripts/harness/engine/guard.py`,
`decide_agent`) exige uma delegação BRIEFED, que exige task → story → sessão triada. Até uma pergunta a um
especialista passa por esse fluxo, e uma mudança de 1 linha exige story + task.

DECISÃO DE PRODUTO JÁ APROVADA PELO USUÁRIO (registre com `ac.py gate plan:DEC-FAIXAS --by founder --decision
approve --note "aprovado em 2026-10-03"` — não pergunte de novo): três faixas, escolhidas pela classe da triagem.

| Faixa | Classe | Exige | Garantias que NUNCA afrouxam |
|---|---|---|---|
| Consulta | `pergunta` | nada no board; delegação de consulta descartável | agente SÓ LEITURA (guard bloqueia escrita); evento no ledger |
| Task avulsa | `trivial`, `pequena` | SÓ a task (story "avulsa" implícita criada pelo motor) | território, `verification_command`, revisão de gate em `pequena` |
| Fluxo completo | `feature`, `risco` | épico → feature → sprint → story → task (como hoje) | todas |

Contrato de nomes (as frentes usam exatamente isto):
- `cs-state ask <agente> "<pergunta>" [--paths "<glob>"…]` → cria delegação `kind: consult` já BRIEFED, imprime o id
  para a `description` do Agent; o guard libera o despacho e marca o subagente como só leitura (PreToolUse de
  Write/Edit/Bash-que-escreve do subagente = bloqueio); ao terminar, a delegação fecha sozinha (`ANSWERED`), sem
  task, sem story, sem review.
- `cs-state add task --quick --agent <a> --title "…" --allowed-path <arq>… --verify-cmd "<cmd>" [--ac …]` → cria a
  task numa story implícita `STORY-AVULSA` da sessão; permitido só com a sessão triada como `trivial` ou `pequena`.
- Promoção obrigatória: task avulsa cujo `allowed_paths` toca >1 território, uma invariante/área congelada ou exige
  >1 agente → recusa com a mensagem "suba a classe: `cs-state session triage --class feature|risco`".
- `cs-state next` e o kernel do orquestrador (template orchestrator.md) passam a indicar a faixa pela classe.

Cenários de aceite = EXTENSÃO DO ORÁCULO (adicione em `evals/harness_scenarios.json` NA ETAPA `oraculo` da rodada 0,
ANTES do `oracle freeze` — é requisito novo, não ajuste para passar):
- CONSULT-1: `ask` sem story/task → Agent despachado é aceito pelo guard; Write do subagente é bloqueado; ledger tem o evento.
- CONSULT-2: despacho de Agent sem `ask` e sem delegação continua bloqueado (a faixa não vira brecha).
- QUICK-1: sessão `trivial` → `add task --quick` cria task sem épico/feature/sprint/story explícitos; verify/accept funcionam.
- QUICK-2: sessão `feature` → `add task --quick` recusado.
- QUICK-3: task avulsa tocando 2 territórios (ou invariante) → recusa com "suba a classe".
- PEQUENA-1: task avulsa em `pequena` só é ACCEPTED com 1 revisão de gate; em `trivial`, sem revisão.
Documente nas docs (docs/02-harness.md, docs/06-referencia-cli.md, MODO-DE-USO.md e SKILL.md "Como usar").

## P0 da rodada 1 — etapa de saneamento ao fim de todo init (`sanitize`)
Problema (medido no repositório real do founder, ~/Repositorios/repositório-piloto (projeto-legado), 2026-10-03): repo com 100 MB,
91 MB de lixo em `.specialists/tmp/` — 15 cópias de exame com `.git` próprio (86 MB), pacotes de entrada (4,1 MB),
rascunhos já registrados, 4 scripts de contorno do executor (`fix_g2.py`, `inspect_g2.py`, `cmp_cards.py`,
`refs_probe.py`) e `harness/__pycache__`; e NENHUM `.gitignore` → um `git add .` commita 91 MB e 15 repositórios
aninhados. NÃO limpe esse repositório (o founder decide); use-o só como evidência (leia, não escreva).

DECISÃO APROVADA (portão `plan:DEC-SANITIZE`, --note "aprovado em 2026-10-03"). Contrato:
- Nova sub-etapa `approve.4 — sanitize` em stages.json5 (antes do `cs-session save` final), check que prova o EFEITO.
- `cs.py sanitize` = plano (lista o que apaga, com tamanhos; não escreve). `cs.py sanitize --apply` = apaga `tmp/`
  inteiro e todo `__pycache__` sob a pasta da skill; grava `<pasta>/.gitignore` com `tmp/`, `memory/index/`,
  `__pycache__/`, `backups/`; antes de apagar, lista no relatório (como DEFEITO da execução) todo script deixado em
  `tmp/` (contorno manual do executor).
- Checagens: nenhum `.git` aninhado fora de `tmp/`; nenhum arquivo de produto alterado (git status só com os caminhos
  do manifesto do emit + `Makefile`/`CLAUDE.md` gerenciados); relatório final diz o tamanho que fica e o que entra no commit.
- Causa: cada cópia de exame é apagada logo após o `probes check` daquele agente (não acumular 15 clones).
Cenários de aceite (oráculo, antes do freeze):
- SANITIZE-1: após init completo, `tmp/` vazio, sem `__pycache__`, `.gitignore` presente; `git status --porcelain`
  só lista caminhos esperados; tamanho da pasta da skill ≤ 5 MB nas 3 fixtures.
- SANITIZE-2: `sanitize` sem `--apply` não apaga nada (hash da árvore igual).
- SANITIZE-3: script deixado em `tmp/` aparece no relatório como contorno antes de ser apagado.
- SANITIZE-4: approve.4 não fecha com `tmp/` não vazio ou sem `.gitignore`.

## P1 da rodada 1 — renomear a pasta gerada de `.specialists/` para `.swarm/`
DECISÃO APROVADA (portão `plan:DEC-SWARM-DIR`, --note "aprovado em 2026-10-03").
- Todo caminho `.specialists/` vira `.swarm/` (CLI, harness copiado, wrappers `.swarm/bin/cs-*`, hooks, templates
  emitidos, prompts, docs, evals/check_run.py, testes). Centralizar o nome numa constante (`cslib.paths`) e um teste
  que falha se `.specialists` aparecer em código/templates fora da migração.
- UM HARNESS SÓ (regra do founder, 2026-10-03): o harness da skill NUNCA coexiste com outro no mesmo repositório —
  nem v8 (harness anterior), nem uma instalação antiga desta skill, nem harness desconhecido, mesmo em pastas diferentes.
  `init` detecta qualquer harness existente (`.swarm/instance.json`, `scripts/harness/`, hooks de terceiros em
  `.claude/settings.json`, `.claude/kernel/`, `.specialists/` legado) e PARA mostrando o plano de substituição.
  Só com `--replace-harness` (portão humano): backup completo do harness antigo em `<pasta>/backups/harness-anterior/`,
  desinstalação (hooks, settings, kernel, scripts, gate de pre-commit dele), IMPORTAÇÃO do conhecimento
  reaproveitável como fatos citáveis (`facts interpret` com origem: invariantes de domínio, ADRs, territórios,
  convenções da placa v8) e só então a instalação. Sem a flag, sai sem escrever nada. Pós-instalação: check de
  "harness único" (um conjunto de hooks, um estado, nenhum resíduo do anterior).
- Migração no `upgrade` (`kind: rename-dir`): alvo legado com `.specialists/` → move para `.swarm/` (é o mesmo harness
  desta skill, não um estranho), reescreve os caminhos nos artefatos emitidos/hooks/settings/Makefile e valida.
Cenários: SWARM-DIR-1 (init novo cria só `.swarm/`; nenhum `.specialists`), SWARM-DIR-2 (repo com harness v8 → init
sem flag não escreve nada e mostra o plano), SWARM-DIR-3 (upgrade de alvo legado renomeia e guards seguem
funcionando — selftest verde), SWARM-DIR-4 (`--replace-harness` num repo v8 — use uma cópia do repo v8 em mktemp:
backup feito, hooks/kernel/scripts do v8 removidos, invariantes do v8 importados como fatos, um único harness ativo,
selftest verde).

## P1 da rodada 1 (logo após a PRIORIDADE MÁXIMA) — comando `upgrade` com versão e migrações
Problema: um repositório que já tem time gerado não tem como receber uma versão nova da skill sem rodar tudo de
novo (inclusive entrevista e aprovação do roster, o que mais custa). Separar "atualizar o mecanismo" de "refazer o
conhecimento".

DECISÃO DE PRODUTO JÁ APROVADA PELO USUÁRIO (registre com `ac.py gate plan:DEC-UPGRADE --by founder --decision
approve --note "aprovado em 2026-10-03"`).

Contrato:
- Skill versionada: `VERSION` na raiz da skill (semver) e `references/migrations.json5`:
  `{version, migrations: [{to, why, actions: [{kind: harness|emit|scan|facts-refresh|schema|cards|probes, ...}]}]}`.
  `scan` leva `layers: [...]`; `schema` leva `script` (conversor idempotente de team.json5/board); `cards`/`probes`
  só quando a migração exige e sempre avisam que haverá reexame.
- Alvo grava `skill_version` e `upgrade_history[]` em `.specialists/run.json5` (o `init` grava a versão atual).
- Alvo LEGADO (gerado antes do versionamento, sem `skill_version`): tratado como `0.0.0-legado`; o upgrade aplica
  todas as migrações desde a primeira e o plano diz "partindo de repositório legado". O founder vai gerar times em
  repositórios reais ANTES desta rodada — esses são os primeiros alvos legados.
- `cs.py upgrade` (sem flags) = PLANO: lê a versão do alvo e a da skill, junta só as migrações no intervalo, lista o
  que muda, o que é preservado e o que fica fora de `.specialists/`. Não escreve nada.
- `cs.py upgrade --apply [--allow-outside]` = backup em `.specialists/backups/upgrade-<de>-<para>/`, roda só as
  ações necessárias, verifica (`harness selftest`, `harness validate --strict --allow-empty`, `emit validate`) e,
  se algo falhar, restaura o backup e sai com exit 1. Sucesso grava a nova versão e uma entrada em `upgrade_history`.
- NUNCA refeito num upgrade (salvo migração explícita): entrevista, roster aprovado, cartões aprovados, memória de
  lições, board/eventos.
- Comando da skill: `/codebase-specialists upgrade` (mostra o plano e pede OK) — acrescente na tabela de argumentos
  do SKILL.md e no MODO-DE-USO.md.
- Regra de manutenção: toda mudança na skill que afete repositórios já gerados vem com entrada em
  `migrations.json5`; um teste (scripts/doctests) falha se `VERSION` mudou sem migração correspondente.

Cenários de aceite (adicionar ao oráculo na etapa `oraculo` da rodada 0, antes do freeze):
- UPGRADE-1: alvo gerado na versão anterior → `upgrade --apply` não reabre entrevista nem roster; cartões e aprovações intactos.
- UPGRADE-2: board, events.jsonl (cadeia de hash válida), memória e lições sobrevivem ao upgrade.
- UPGRADE-3: `upgrade` sem `--apply` não escreve nenhum arquivo (comparar hashes da árvore antes/depois).
- UPGRADE-4: verificação falhando após aplicar → restauração completa do backup e exit 1.
- UPGRADE-5: migração com `scan layers: [L2]` refaz só a camada L2 (demais fatos com o mesmo hash).
- UPGRADE-6: alvo legado (run.json5 sem `skill_version`, gerado pela skill da iteração 4 — use um alvo de
  iteration-4/) → `upgrade --apply` funciona sem reabrir entrevista nem roster.

## FORA DO ESCOPO desta rodada (não implementar agora)
Estado como árvore navegável (épico/feature/sprint/tasks em pastas, um arquivo por item) — é a rodada SEGUINTE e
depende da task avulsa e da pasta `.swarm/` desta. Especificação: RODADA-SEGUINTE.md (cópia em
codebase-specialists/docs/ROADMAP-rodada-seguinte.md). Só não tome decisões nesta rodada que a contradigam
(ex.: a task avulsa deve ter id, TIPO (US|BUG|FIX) e arquivo próprios, prontos para virar
`.swarm/state/tasks/<aaaa-mm-dd>-<nn>-<TIPO>-<slug>.json5`; não crie nível de story novo — na rodada seguinte
story deixa de existir e vira tipo da task; hierarquia final: épico → sprint → feature → task).

## OBRIGATÓRIO em toda rodada — workflow inteiro do harness testado de ponta a ponta (founder, 2026-10-03)
Motivo: o founder achou num harness instalado uma delegação em ESCALATED sem nenhuma transição de saída (máquina
trancada) — e 480 testes passavam, porque nenhum testava o WORKFLOW, só funções. O oráculo de toda rodada inclui:
- `scripts/harness/tests/test_maquinas_vivacidade.py` (invariante permanente): nenhum estado sem saída a não ser
  terminal declarado; "esperando humano" (ESCALATED, ABSTAINED) nunca terminal e com saídas retomar/trocar/descartar;
  todo estado alcançável.
- Uma suíte WORKFLOW-E2E (CLI real + guard real, repo temporário) que percorre a orquestração inteira e cada desvio:
  épico → sprint → feature(s) → tasks (e as faixas consulta/avulsa) com: despacho em ondas sem colisão, submit,
  verify falho → reject → retry, review FAIL/NEEDS_SPECIALIST, escalate → retomar | trocar de agente | descartar,
  abstain → idem, reroute, fechamento de cada nível, retomada de sessão (`cs-session save`/`load`) no meio, modo
  autônomo do início ao fim com uma escalada no meio. Cada caminho termina num estado coerente (validate --strict OK)
  e nenhum fica trancado. Entra no oráculo ANTES do freeze; nenhuma frente pode editá-lo.

## Oráculo (já existe — calibre, não reconstrua)
- Corretor: ~/.claude/skills/codebase-specialists/evals/check_run.py <alvo> <GROUND_TRUTH> --mode setup --out grading.json
  GROUND_TRUTH em evals/fixtures/<py-billing|ts-shop|go-polyglot>/GROUND_TRUTH.json; fixtures: evals/fixtures/build.sh <f> <dest>.
- Resumo Q×S: evals/summarize.py. Qualidade [Q] é a métrica comparável com o baseline; estrutura [S] é da skill.
- Baselines sem a skill (não rode de novo): iteration-1/<eval>/without_skill → [Q] 9/13, 10/13, 10/13.
- Calibração: já se sabe que o corretor erra em negação ("X não existe" lido como afirmação) — conferir à mão ≥2
  asserções por configuração antes de confiar; mudança no corretor só via `ac.py oracle change --why --evidence`.

## Passo 0 — fechar a medição pendente da iteração 4 (barato, ANTES de corrigir)
Duas execuções ficaram pausadas no meio da validação; retome cada uma (uma por vez) com a própria skill:
- iteration-4/py-billing-setup-vague/with_skill/target  (parou em validate.3)
- iteration-4/go-polyglot-setup-vague/with_skill/target (parou em validate.2)
Num subagente por execução: "No repositório <target>, rode `/codebase-specialists retomar`; sem humano: aprovações
com `--by eval-sim --simulated`; liste TODO contorno manual em <outputs>/notes.md sob 'CONTORNOS MANUAIS'."
Registre as duas como rodada 0 da campanha (`ac.py run record`) junto com a do ts-shop já concluída
(iteration-4/ts-shop-setup-vague: GO simulado, [Q] 13/13 real, 5 contornos manuais).

## Critério de parada (aprovar com o usuário em intake.3)
Os 6 cenários da PRIORIDADE MÁXIMA (CONSULT-1/2, QUICK-1/2/3, PEQUENA-1), os 6 do upgrade (UPGRADE-1..6), os 4 do saneamento (SANITIZE-1..4), a vivacidade das máquinas, a suíte WORKFLOW-E2E e os 4 da pasta/harness único (SWARM-DIR-1..4)
passando; rodada --fast nos 3 alvos:
≥2/3 GO; ZERO contornos manuais; [Q] ≥ baseline nos 3; todas as suítes verdes em python3 (3.13) e
/usr/bin/python3 (3.9.6). Sem progresso em 2 rodadas → escalar ao usuário.
Ordem da rodada 1 (frentes com arquivos disjuntos):
1. 3 faixas de interação (engine/cmds/guard do harness) — PRIMEIRO no plano.
2. `sanitize` (stages.json5 approve.4 + cs.py sanitize + limpeza das cópias de exame) — em paralelo.
3. `upgrade` (cs.py upgrade, VERSION, migrations.json5, init grava skill_version) — em paralelo.
4. Demais P0 (existência no --fast, G4 com cartão alterado) — em paralelo, sem dividir arquivos com 1–3.
5. Rename `.specialists/` → `.swarm/` — POR ÚLTIMO, depois de 1–4 integradas (toca quase todos os arquivos; não
   paralelizar com nada) — inclui a migração `rename-dir` no upgrade.

## Orçamento e custo (o usuário tem limite de uso de 5 h)
- Máx. 2 rodadas. Execuções de avaliação UMA POR VEZ (não 3 em paralelo); frentes de correção ≤3 em paralelo.
- Ao passar de ~50% da janela de uso, pare num checkpoint (handoff em disco) e pergunte se continua.
- Execuções interrompidas: retome pelo disco (`/codebase-specialists retomar`), nunca do zero.

## Portões humanos
Critério de parada, decisões de produto, commit/push (só a pasta codebase-specialists/ do repo ~/.claude/skills;
nunca o workspace, que tem repositórios git aninhados).

## Entrega
Relatório curto: decisão (parar/continuar/escalar), tabela [Q]×[S]×custo com baseline, contornos manuais restantes,
o que o oráculo pode estar favorecendo, e uma seção "lições para a auto-correcao" (o que no ciclo dela ajudou ou
atrapalhou nesta campanha real).
```

---

## Notas para você (não fazem parte do prompt)
- Custo estimado: passo 0 ≈ 2 execuções curtas; cada rodada ≈ 3 frentes + 3 execuções em série (~25–35 min cada).
- Se quiser só fechar a medição sem corrigir nada, rode apenas o "Passo 0" e peça o relatório.
- Se testar num repositório seu antes, anote os atritos e acrescente ao prompt na seção "Alvo e contexto".
