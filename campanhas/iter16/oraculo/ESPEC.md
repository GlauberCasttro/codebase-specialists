# ESPEC — oráculo campanha-iter16 (uso real: cobaia cobaia .NET, .NET)

Correções feitas direto na skill, sem teste, durante o teste real na cobaia .NET. O oráculo `test_uso_real.py`
(unittest puro, Python 3.9+, alvos temporários) **prova o defeito** (falha com os arquivos anteriores) e **prova a
correção** (passa com a skill viva). Skill sob teste: `$CS_SKILL_DIR` (padrão `~/.claude/skills/codebase-specialists`).

Rodar (desta pasta): `python3 -m unittest -v test_uso_real`; placar por requisito: `python3 medir.py`.

**2ª rodada (ampliação U2b, U5–U11).** Medição em `base.txt` (python3 3.13.3 e /usr/bin/python3 3.9.6, iguais):

| req | ANTES (HEAD 18e3496) | VIVA | situação |
|---|---|---|---|
| U1 BOM | 4/11 | 11/11 | corrigido |
| U2 dotfile | 6/6 (*) | 6/6 | corrigido (já no HEAD; defeito provado contra exam.py de 2c90621: 4 falhas) |
| U2b fim de frase / `.NET` | 0/2 | 0/2 | **a implementar** |
| U3 refino no --fast | 4/8 | 8/8 | corrigido |
| U4 history | 3/5 | 5/5 | corrigido |
| U5 check-diff pós-aceite + orchestrator | 3/7 | 3/7 | **a implementar** |
| U6 linha da aresta C# | 0/1 | 0/1 | **a implementar** |
| U7 `using` em string C# | 0/1 | 1/1 | corrigido |
| U8 critério em `dependency` | 0/1 | 1/1 | corrigido |
| U9 `why` sem tópico genérico | 0/1 | 1/1 | corrigido |
| U10 `why` por documento | 1/2 | 2/2 | corrigido |
| U11 cópia do exame com painel pendente | 0/1 | 1/1 | corrigido |
| U12 `namespace` em string C# | 1/2 | 1/2 | **a implementar** |
| total | 22/48 | 40/48 | os 8 restantes = U2b (2), U5 (4), U6 (1), U12 (1) |

**Versão ANTES** = `git archive 18e3496 codebase-specialists` em `scratchpad/iter16-antes/` (arquivos alterados
desde o HEAD na versão do HEAD; os novos ausentes). (*) O ramo de dotfile do PATH_RE entrou em 9d1ab30, por isso U2
passa no ANTES; `base.txt` traz a prova contra `exam.py` de 2c90621 e uma mutação de controle do U5.

1ª rodada (U1–U4): ANTES = viva com exam.py de 2c90621 e context/cards/generate/probes.md do HEAD → 16 falhas de 30;
VIVA 30/30.

Legenda: **D** = teste de defeito (falha ANTES, passa VIVA). **R** = regressão/sem brecha (passa nos dois).

## U1 — BOM UTF-8 em C#
Fixture: repo git com 5 `.cs`; BOM só em `SwiftMapException.cs` (`namespace` na linha 1) e `Worker.cs` (`using`
na linha 1). Cada aresta isola um lado: Runner(sem BOM)→SwiftMapException(BOM) = lado `namespace`;
Worker(BOM)→Log(sem BOM) = lado `using`; Plain→Log = sem BOM. Mudança: `scripts/scan/context.py` `text()` decodifica
com `utf-8-sig`.

| Requisito | Teste | Tipo |
|---|---|---|
| aresta existe (lado namespace) | `TestU1BomGrafoDoScan.test_namespace_na_linha_1_com_bom_e_resolvido` | D |
| sem in=0 indevido | `TestU1BomGrafoDoScan.test_arquivo_com_bom_nao_fica_com_in_zero` | D |
| aresta existe (lado using) | `TestU1BomGrafoDoScan.test_using_na_linha_1_com_bom_e_resolvido` | D |
| namespace interno não vira import externo | `TestU1BomGrafoDoScan.test_namespace_interno_nao_vira_dependencia_externa` | D |
| grafo exato (nem a menos nem a mais) | `TestU1BomGrafoDoScan.test_grafo_exato` | D |
| leitura sem BOM / linha 1 = declaração | `TestU1BomLeituraDoContexto.test_bom_nao_aparece_no_texto`, `test_linha_1_com_bom_e_a_declaracao` | D |
| sem BOM continua igual | `TestU1BomGrafoDoScan.test_regressao_sem_bom_continua_igual`, `TestU1BomLeituraDoContexto.test_regressao_texto_sem_bom_identico_ao_bruto`, `test_regressao_feff_no_meio_e_preservado` | R |
| pré-condição da fixture | `TestU1BomGrafoDoScan.test_precondicao_fixture_tem_bom_so_onde_deve` | R |
| U6: aresta C# registra a linha do `using` (Runner→Exc: 2; Worker(BOM)→Log: 1; Plain→Log: 2) | `TestU1BomGrafoDoScan.test_u6_aresta_csharp_registra_a_linha_do_using` | D (a implementar) |
| U7: `using Cobaia.Core;` em raw string depois de `public sealed class` não é aresta | `TestU1BomGrafoDoScan.test_u7_using_em_string_literal_nao_e_import` | D |

## U2 — dotfile no exame (`probes/exam.py` PATH_RE / `cites`)
| Requisito | Teste | Tipo |
|---|---|---|
| U2b: dotfile sem linha em fim de frase (`o arquivo é .editorconfig.`) | `test_u2b_dotfile_em_fim_de_frase_sem_linha` | D (a implementar) |
| U2b: `.NET 8` / `.NET 9.` / `(.NET Framework 4.8)` não vira caminho | `test_u2b_dotnet_nao_vira_caminho` | D (a implementar) |
| `.editorconfig:3` (solto, em prosa, crase, parênteses, fim de frase, vírgula) | `TestU2DotfileNoExame.test_editorconfig_na_raiz_com_linha` | D |
| `.gitignore:2`, `.env:1`, `.eslintrc:10`, `.prettierrc:4` | `test_outros_dotfiles_na_raiz` | D |
| efeito no exame: sonda `location` com gabarito `.editorconfig:3` aprova | `test_sonda_de_localizacao_em_dotfile_e_pontuada` | D |
| `src/.eslintrc:10` | `test_eslintrc_em_subpasta_com_linha` | R (*) |
| caminhos normais intactos (`.github/workflows/ci.yml:7`, `src/.eslintrc.json:3`, `docs/.env.example:2`, `Makefile:4`, `./src/app.py:3`…) | `test_regressao_caminhos_normais_intactos` | R |
| sem falso positivo: `e.g.`, `i.e.`, `v1.2`, fim de frase, `3.14`, `Ok.Próximo` não viram dotfile nem caminho+linha | `test_sem_falso_positivo_de_dotfile_em_prosa` | R |

(*) `src/.eslintrc:10` **já casava antes** pelo ramo `(?:[\w.@-]+/)+[\w.@-]+`: só o dotfile na RAIZ era defeito.
"Sem falso positivo" é medido sobre dotfile/caminho+linha: `e.g` e `v1.2` continuam extraídos como "caminho" sem
linha nas DUAS versões (inofensivo: não existe no inventário e não tem `/`, então não pesa em nenhum tipo de sonda).

## U3 — refino no --fast (sem painel) — `scripts/team/cards.py` `card_revise`
Fixture: repo/fatos sintéticos de `team/tests/synth.py` + `derive`; cartão de `dev-billing` via `card set`; sem
`.swarm/panel/dev-billing.json5`; `.swarm/probes/cycles.json5` escrito como fixture no formato de `probes/final.py`.

| Requisito | Teste | Tipo |
|---|---|---|
| reprovado + refino aberto → `revise --file` grava `refines[cycle=1]` (não `revised`, não `existence_fixes`) | `TestU3RefinoNoFastSemPainel.test_reprovado_com_refino_aberto_revisa_com_file` | D |
| idem `revise --note` (sem mudança) | `test_reprovado_com_refino_aberto_revisa_sem_mudanca_com_note` | D |
| um refino por ciclo reprovado (2º recusado com a msg do painel; novo FAIL libera mais um) | `test_refino_e_unico_por_ciclo_reprovado` | D |
| refino sem painel ainda roda o check de existência do cartão novo (nada gravado) | `test_refino_sem_painel_ainda_checa_existencia_do_cartao_novo` | D |
| (a) sem refino e sem falta, sem painel → recusa "painel … não consolidado (.swarm/panel/…)"; rt.4 não abre | `test_sem_ciclo_sem_falta_rt4_sem_painel_recusada` | R |
| exame APROVADO não abre refino | `test_exame_aprovado_nao_abre_refino` | R |
| reprovação de OUTRO agente não abre refino | `test_reprovacao_de_outro_agente_nao_abre_refino` | R |
| (b) conserto de existência sem painel continua (e, consertado, volta a exigir painel) | `test_conserto_de_existencia_sem_painel_continua` | R |

## U4 — sonda `history` — `scripts/probes/generate.py` + `references/probes.md`
Fixture: `scan/tests/synth.py` (git real: `init` + `fix: bug no limite de itens …`) + um commit POSTERIOR
`fix: corrige de novo o limite …` no mesmo arquivo (a armadilha de "qual commit corrigiu X"); `cs.py scan --no-exec`
→ `derive` → `generate`.

| Requisito | Teste | Tipo |
|---|---|---|
| pergunta pelo sha do commit cujo ASSUNTO é o citado; texto (fora do assunto) não diz corrigiu/fixed | `TestU4SondaHistory.test_pergunta_e_pelo_sha_do_commit_com_aquele_assunto` | D |
| `references/probes.md` linha HISTÓRIA: sem "corrigiu", "sha … assunto", fonte `history.fixes`, critério prefixo | `test_probes_md_linha_historia_coerente` | D |
| gabarito = o próprio commit do assunto citado (sha único por `git log`) | `test_gabarito_e_o_proprio_commit_do_assunto_citado` | R (**) |
| exame aprova o sha do assunto e reprova o do commit posterior | `test_exame_aprova_o_sha_do_assunto_e_reprova_o_commit_posterior` | R |
| pré-condição: há sonda history | `test_precondicao_ha_sonda_history` | R |

(**) O gabarito já era o próprio commit antes; o defeito era só o TEXTO da pergunta, que mandava procurar outro commit.

## U5 — check-diff depois do aceite (`scripts/harness/engine/guard.py` `check_diff`) + orchestrator
Fixture: repo git com estado em ÁRVORE (`cs-state init`), task avulsa US de `dev-billing` com
`allowed_paths = [src/billing/discount.py]`, levada pela M2 inteira pela CLI real (`start`, `dispatch --manual`,
`submit`, `verify`, `review PASS`, `accept`); `guard.py check-diff --root` em subprocesso (é o que o pre-commit roda).

| Requisito | Teste | Tipo |
|---|---|---|
| ACCEPTED + task aberta → libera os allowed_paths (working tree) | `TestU5CheckDiffDepoisDoAceite.test_aceita_e_aberta_libera_os_allowed_paths` | D (a implementar) |
| idem no pre-commit (`--staged`) | `test_aceita_e_aberta_libera_no_pre_commit_staged` | D (a implementar) |
| ACCEPTED, mas arquivo fora de qualquer allowed_paths → barra (e só ele é acusado) | `test_aceita_mas_arquivo_fora_continua_barrado` | D/R (a implementar: hoje acusa os dois) |
| task fechada (`cs-state close`, archive/) → barra (working tree e `--staged`) | `test_fechada_barra` | R |
| criada / iniciada (READY, delegação BRIEFED) → barra | `test_briefed_ou_ready_barra` | R |
| `CS_GUARD_OFF=1` sem efeito (BRIEFED e fechada) | `test_guard_off_nao_afeta_o_check_diff` | R |
| orchestrator gerado (`init --platforms claude-code` + `harness install` + `emit`): em `## Como o fluxo anda`, um passo cita commit dos `allowed_paths`, `PASS` e `cs-state close`, com o commit ANTES do close | `TestU5OrchestratorInstruiCommitAntesDoClose.test_fluxo_manda_commitar_allowed_paths_depois_do_pass_e_antes_do_close` | D (a implementar) |

Mutação de controle (em `base.txt`): somar `"ACCEPTED"` à tupla de `check_diff` faz `test_fechada_barra` e
`test_guard_off…` falharem — no estado em árvore a task fechada CONTINUA em `board["tasks"]` com a delegação
ACCEPTED. A correção precisa distinguir task arquivada (zona `archive/`), não só o estado da delegação.

## U8–U11 — mudanças de produto da 2ª rodada cobaia .NET (`probes/generate.py`, `probes/exam.py`)
Fixture U8–U10: `team/tests/synth.py` + docs e fatos de rationale acrescentados (tópico "O que foi feito"; tópico
"Decisões tomadas" em 3 documentos; "cache de precos em memoria" como controle; ADR de 30 linhas) → derive → generate.

| Requisito | Teste | Tipo |
|---|---|---|
| U8 pergunta de `dependency` traz `critério: … import …` e exclui string/comentário | `TestU8aU10Sondas.test_u8_dependency_traz_o_criterio_de_importa` | D |
| U9 sem `why` de tópico genérico nem de tópico repetido em ≥3 fatos; específico continua | `test_u9_why_sem_topico_generico_nem_repetido` | D |
| U10 `why` sem key_terms: linha 20 do documento-fonte (gabarito na linha 1) passa e fica `panel_pending` | `test_u10_why_sem_key_terms_aceita_qualquer_linha_do_documento` | D |
| U10 regressão: outro documento reprova; linha do gabarito passa; com key_terms a janela ±3 exige o termo | `test_u10_regressao_outro_documento_e_key_terms_continuam_valendo` | R |
| U11 `probes exam-pack --out` + respostas + `probes check`: com `why` pendente a cópia `<out>/repo` FICA; após `panel why … --verdict PASS` e novo check, sai | `TestU11CopiaDoExameComPainelPendente.test_copia_fica_com_painel_pendente_e_sai_depois_do_painel` | D |

U8 para `.cs` (critério `using <namespace>`) não é exercitado pelo banco (o repo sintético é Python); o texto do
critério C# só é coberto pelo teste interno da skill (`IMPORT_CRITERION[".cs"]`).

## U12 — `namespace` dentro de string C# (`scripts/scan/l1_graph.py` `CS_NAMESPACE`, mapa `_cs_ns`)
Fixture: `tests/Gen/G.cs` com `namespace Fake.Ns;` só dentro de raw string (e `"namespace Other.Ns { }"` em string
comum); `src/U.cs` com `using Fake.Ns; using Other.Ns; using Real.Ns;`; `src/Real.cs` declara `Real.Ns` (controle).

| Requisito | Teste | Tipo |
|---|---|---|
| `using Fake.Ns;` não vira aresta para o arquivo cuja "declaração" está na string | `TestU12NamespaceEmStringCSharp.test_namespace_em_string_nao_vira_alvo_de_using` | D (a implementar) |
| namespace real continua resolvendo (U.cs → Real.cs) | `test_regressao_namespace_real_continua_resolvendo` | R |

**Limites documentados, sem teste (decisão do coordenador):** `CS_FIRST_TYPE` corta os `using` na 1ª declaração de
tipo do ARQUIVO — um 2º bloco `namespace B { using C; … }` depois de um tipo perde o `using C`; `global using` continua
ignorado pelo scanner C#.

## Mudanças em TESTES da skill (2ª rodada) — viram mudança oficial?
- `scripts/sanitize/tests/test_sanitize.py` (`ExamCopyRemovedAfterCheck._exam`): **sim, obrigatória** — registro em
  `mudanca-oficial/PORQUE-sanitize-iter16.md` + `mudanca-oficial/test_sanitize-iter16.patch` (troca o `if pend:` por
  pré-condição explícita; 8/8 OK com o patch na viva). Com o produto
  novo (U11) a versão do HEAD reprova contra a skill viva (medido: 2 falhas em 8) — a cópia fica enquanto o painel
  `why` está pendente; o ajuste registra os vereditos e roda o check de novo antes de afirmar a remoção. Ressalva:
  o ramo `if pend:` é condicional; se o banco do synth deixar de ter `why` para `dev-billing`, o novo contrato deixa de
  ser exercido ali (o oráculo U11 exige a pré-condição).
- `scripts/probes/tests/test_iter6_cobaia_dotnet.py` (novo): **sim, como regressão interna**, mas não substitui o
  oráculo: testa NOMES internos (`CS_FIRST_TYPE`, `CS_USING`, `IMPORT_CRITERION`, `GENERIC_TOPICS`, `_topic_key`)
  — contra o HEAD nem importa (ImportError), então não "falha pelo defeito", só quebra. Os testes observáveis
  equivalentes estão aqui (U7–U10). Os dois casos que ele cobre e o oráculo não: `using` dentro de bloco
  `namespace A { using B.C; class X {} }` e arquivo sem tipo (top-level) — vale mantê-los.
- `docs/12-…` e `docs/README.md`: documentação; sem teste. `docs/12` diz "probes 78 OK (6 novos)" — o arquivo novo
  tem 6 testes, coerente.

## Achados (correção incompleta / fora do escopo)
1. `scripts/probes/exam.py:26` — U2b, ainda aberto: dotfile em fim de frase sem linha não é citado; `.NET` vira
   caminho (inofensivo para a nota hoje). Sugestão: lookahead `(?![\w/]|\.\w)` e excluir `.NET` (ou exigir minúscula/
   dígito no nome do dotfile, ex. `\.[a-z][\w-]{1,30}`).
2. `scripts/team/cards.py:419-425` — sem painel, com refino aberto E falta de existência no cartão atual, o `--file`
   conta como refino (consome o slot), não como conserto de existência. Defensável; diverge do caminho com painel.
3. `scripts/scan/l1_graph.py:304` (`edge_line`) — U6, ainda aberto: para C# a linha da aresta é 0 (procura o nome do
   arquivo-alvo na linha do `using`, que cita o namespace). Precisa casar o namespace do alvo (`ctx._cs_ns`).
4. (limite documentado, sem teste) `scripts/scan/l1_graph.py:30` (`CS_FIRST_TYPE`, novo) — corta os `using` na 1ª declaração de tipo do ARQUIVO:
   arquivo com vários blocos `namespace A { class X {} } namespace B { using C; … }` perde o `using C`; e uma linha de
   comentário de bloco começando por `class`/`enum`/`record`… antes dos usings corta tudo. Raros; registrar.
   `global using` continua ignorado (pendência já anotada em docs/12).
5. `scripts/scan/l1_graph.py:401` — virou o requisito **U12** (a implementar).
