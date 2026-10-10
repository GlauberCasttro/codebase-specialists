# ESPEC — oráculo da campanha iter19 (B-14, versão 0.11.0)

Oráculo `test_iter19.py` (unittest puro, Python 3.9+, só stdlib, repositórios git temporários, CLIs reais em
subprocesso — `cs.py`, o motor INSTALADO no alvo em `.swarm/harness/{state,session,mem,auto}.py` e o hook git de
verdade, sem mock). Skill sob teste: `$CS_SKILL_DIR` (padrão: a raiz deste projeto). Rodar (desta pasta):
`python3 -m unittest -v test_iter19`; placar por CA: `python3 medir.py`. Cerca de 30 s por Python no HEAD.

Base medida em `base.txt`: HEAD 97a1718 (0.10.1), produto sem diff, com python3 3.13 e /usr/bin/python3 3.9.6.
Resultados iguais nos dois: **28 D falham e 11 R passam** (39 testes).

Legenda: **D** = defeito (falha na base e passa depois da correção). **R** = não-regressão (passa antes e depois).
O `medir.py` classifica como R os testes cujo nome contém `regressao|controle|continua|intacta`.

## Fixture (alvo realista)
- **Skill antiga REAL:** `git archive 97a1718` deste repositório (commit da 0.10.1), extraída num diretório
  temporário; nada é escrito no repositório. Outra cópia: `$CS_OLD_SKILL_DIR`.
- **Alvo:** repositório da fixture do emit (time: dev-billing, dev-web, reviewer, qa) + `tests/test_ok.py` (verde),
  `accept/test_accept.py` (vermelho: a feature tem o que entregar) e `spec/feature.md`; `cs.py init`,
  `harness install`, `emit`, commit; depois `harness install --git-hook` (o hook só é ligado depois do commit da
  geração: **a fixture nunca usa `--no-verify`**). Todo commit usa `-c core.hooksPath=<alvo>/.git/hooks`.
- **Estado povoado pelo motor instalado no alvo** (`populate`): épico EPC-001 › SPR-001 › FEA-001 em `state/`;
  `FEA-001/01` US **iniciada com AC-1 e AC-2** (alvo do amend); `FEA-001/02` fechada pela M2 inteira (dispatch
  manual, submit, verify, review, accept, commit pelo hook, close) → `archive/`; story composta US-001 (dev-billing +
  dev-web; a task US-001/01 recebe um amend de allowed_paths antes do start); avulsa fechada → `archive/tasks/<a>/<m>/`;
  avulsa fechada e **reaberta**; BUG e CHORE no `backlog/` (o CHORE é planejado na sprint: alias BKL/02); task da
  sprint **não iniciada** com AC-1 (alvo do amend não iniciado); FEA-002 criada no backlog e **movida** para a
  SPR-001 (histórico com `para`); lição do cs-mem; mandato M5 `MAN-001` PROPOSED; carimbo de sessão. Tudo commitado
  pelo pre-commit. A fixture confere (senão para com mensagem `fixture: …`, antes de qualquer asserção de CA): alvo limpo, cadeia íntegra, **≥ 30 eventos** (medido:
  43), itens nas 3 zonas e `cs-state validate` verde.
- Dois moldes, construídos 1 vez por execução: `new` (gerado e povoado pela skill SOB TESTE) para CA-01..CA-04 e
  parte do CA-06; `old` (skill 0.10.1 real) para CA-05, CA-06 e a leitura de chaves pt do CA-02. Cada teste que
  escreve trabalha numa cópia (`copytree`).
- "Arquivo de estado de entidade" = todo arquivo em `.swarm/{backlog,state,archive}/` exceto `*.jsonl`, `*.md`,
  `state/memory/**` (cs-mem, fora) e `**/mandatos/**` (mandato M5: só formato, chaves pt — fora da varredura de
  chaves). Inclui `state/sessoes/*` (carimbo de sessão). Itens da árvore = os mesmos sem as sessões.
- Leitura TOLERANTE (`load_any`: JSON, senão o parser JSON5 da fábrica `cslib.json5io`) e aceitação das chaves
  antigas ou novas (`crit_ids`, `history`, `action`) onde o CA NÃO é o formato (CA-03), para cada D falhar pelo
  motivo do seu CA.

| CA | D (base) | R (base) | total base |
|---|---|---|---|
| CA-01 JSON padrão em ordem de leitura | 0/6 | 1/1 | 1/7 |
| CA-02 chaves em inglês; leitura das antigas | 0/5 | 1/1 | 1/6 |
| CA-03 amend refletido no arquivo | 0/4 | 2/2 | 2/6 |
| CA-04 cs-state show | 0/4 | — | 0/4 |
| CA-05 migração automática no upgrade | 0/7 | 2/2 | 2/9 |
| CA-06 o que não muda continua igual; 0.11.0 | 0/2 | 5/5 | 5/7 |
| total | 0/28 | 11/11 | 11/39 |

## CA-01 — JSON padrão em ordem de leitura (molde `new`)
| Requisito | Teste | Tipo |
|---|---|---|
| todo arquivo de entidade e de sessão termina em `.json` e `json.loads` aceita; a fixture tem os 5 kinds | `TestCA01.test_ca01_entidades_e_sessao_sao_json` | D |
| o texto é exatamente `json.dumps(conteúdo, indent=2)` (com `ensure_ascii` False ou True; `\n` final opcional): indent 2, um item de lista por linha, e reserializar dá os mesmos bytes | `test_ca01_indent_2_um_item_por_linha_mesmos_bytes` | D |
| itens da árvore: `id` primeiro; as chaves presentes de `id, kind, type, title, agent, allowed_paths, protected_paths, as_a, i_want, so_that, acceptance_criteria` nessa ordem e antes de qualquer outra; `history` por último; na task iniciada `title` < `agent`, `so_that` < `acceptance_criteria` < `created_at`/`started_at` | `test_ca01_ordem_de_leitura_history_por_ultimo` | D |
| `_generated_by` é campo (string não vazia) e o arquivo não começa com comentário | `test_ca01_generated_by_e_campo` | D |
| projeção em `.engine/projection.json` (sem `projection.json5`), JSON indent 2 | `test_ca01_projecao_json` | D |
| depois de `start` de task, `new task` e `cs-session save`, tudo continua `.json` no layout; validate verde | `test_ca01_gravacoes_seguintes_sao_json` | D |
| `cs-state validate` verde no alvo povoado e depois de gravar | `test_ca01_validate_continua_verde` | R |

**Critérios:** `_generated_by` fica FORA da conferência de ordem (posição livre). A ordem da projeção não é conferida
(não é entidade); só formato e layout. "Mesmos bytes ao serializar 2 vezes" é provado pelo ponto fixo do
`json.dumps` (acima) e pela idempotência do apply (CA-05). Chave desconhecida "no fim, em ordem alfabética, antes de
history" não é provocável pela CLI sem editar arquivo: coberta só pelo "antes das demais / history por último".

## CA-02 — chaves em inglês, leitura das antigas
| Requisito | Teste | Tipo |
|---|---|---|
| nenhuma chave (em qualquer nível) do conjunto pt traduzido: `tipo como quero para criterios teste reproducao motivo aceite epico objetivo metrica meta reaberta reaberturas historico acao de entregue devolvido metricas origem tentativas status_m2 blocos titulo linhas` | `TestCA02.test_ca02_nenhuma_chave_pt_nas_entidades` | D |
| task: `type`, `as_a/i_want/so_that`, `acceptance_criteria[{id, gherkin, test}]`, `history[].action`; story: `so_that` (e sem `to`); BUG `failing_test`; CHORE `reason` | `test_ca02_task_story_com_chaves_em_ingles` | D |
| **mapa por caminho**: feature movida tem `history[]` com `action: "move"` e `to: "SPR-001"` (sem `so_that`); task planejada tem `history[].from` = o id antigo; feature `acceptance_cmd` | `test_ca02_historico_para_vira_to_por_caminho` | D |
| épico `objective/metric`; sprint `goal/epic`; fechada `closed{delivered, returned, metrics{attempts, m2_status}}`; reaberta `reopened: 1`, `reopenings[1]`; sessão `blocks[{title, lines}]` | `test_ca02_epico_sprint_fechada_reaberta_sessao` | D |
| alvo 0.10.1 (chaves pt) + `cs.py harness install` da skill sob teste, SEM upgrade: `cs-state start US-001/01` grava o arquivo da task sem chave pt e com `acceptance_criteria == [AC-1, gherkin, test]` lido do pt; validate verde | `test_ca02_le_chaves_pt_e_grava_em_ingles` | D |
| idem: o `brief` da task criada em pt traz o critério e o escopo | `test_ca02_le_chaves_pt_brief_continua` | R |

**Critérios:** mapa da E2 F3 com as decisões do founder (`para` da story → `so_that`; `para` do histórico → `to`;
`de` → `from`). Valores em pt (`kind: "epico"`, `acao: "criado"` → `action: "criado"`), pastas (`epicos/`,
`sessoes/`) e chaves do mandato M5 ficam. "O motor lê o arquivo antigo" é provado pelo motor novo operando um alvo
NÃO migrado (edge "mistura de .json5 e .json": a leitura aceita os dois); recusar operar até migrar reprova o CA.

## CA-03 — amend refletido no arquivo (molde `new`, cópia por teste)
`--after` usado nos dois casos (formato da M2, o mesmo do `cs-state amend` de hoje):
`[{"id": "AC-1", "criterion": "<gherkin>", "verified_by": "test:tests.test_ok"}, ...]`.
| Requisito | Teste | Tipo |
|---|---|---|
| task iniciada com AC-1 e AC-2 → `amend --field acceptance_criteria` só com AC-1 → o arquivo lista só AC-1 (sem o texto do AC-2); validate verde | `TestCA03.test_ca03_amend_iniciada_some_do_arquivo` | D |
| o `history` do arquivo ganha 1 entrada `action: amend` com `before` (com AC-2), `after` (com AC-1, sem AC-2) e `reason` = o motivo | `test_ca03_amend_iniciada_historico_antes_depois_motivo` | D |
| amend → M2 inteira → close → `reopen` → `start`: o arquivo não volta a ter o AC-2 e o `brief` da nova M2 não traz o AC-2 | `test_ca03_reopen_nao_ressuscita_ac2` | D |
| task NÃO iniciada: `amend --field acceptance_criteria` (AC-1 + AC-3 novo) é aceito (exit 0), o arquivo lista AC-1 e AC-3 com o texto novo, o history registra o motivo, e o `start` seguinte usa o AC-3 no `brief` | `test_ca03_amend_nao_iniciada_acceptance_criteria` | D |
| amend de `allowed_paths` em task não iniciada continua refletido (R7, iter18) | `test_ca03_amend_allowed_paths_nao_iniciada_continua` | R |
| amend de campo não espelhável (`goal`) em task iniciada continua aceito (só na M2); validate verde | `test_ca03_amend_campo_nao_espelhavel_continua` | R |

**Critérios:** o teste lê as chaves antigas OU novas (`acceptance_criteria|criterios`, `history|historico`,
`action|acao`) para falhar pelo amend, não pelo formato. As chaves `before/after/reason` do histórico já são as do
`tree.amend` de hoje.

## CA-04 — cs-state show (molde `new`, cópia da classe)
| Requisito | Teste | Tipo |
|---|---|---|
| `show FEA-001/01`: exit 0; Markdown (linha `#`, `##` ou `###` com o título "Aplicar cupom"); id, agente `dev-billing`, escopo `src/billing/coupons.py`, AC-1 e AC-2 com o gherkin, estado (`BRIEFED` ou `READY`), histórico resumido (`start`) | `TestCA04.test_ca04_show_task_iniciada` | D |
| `show BKL/02` (alias do CHORE planejado) mostra o id atual e o título | `test_ca04_show_por_alias` | D |
| `show` da story (título + critério), da feature (título + comando de aceite) e da task fechada (título + `archive` no estado) | `test_ca04_show_story_feature_e_arquivada` | D |
| id inexistente: exit ≠ 0 e o erro cita o id pedido | `test_ca04_show_inexistente_sai_com_erro_citando_id` | D |

**Critério "sem escrever nada":** toda chamada de `show` compara o retrato (sha256 de todo arquivo do alvo fora de
`.git/`) antes e depois. Calibrado: `find`, `tree`, `check` e `validate` não mudam o retrato no HEAD (`brief`
muda o índice da memória, por isso não serve de controle).

## CA-05 — migração automática no upgrade (molde `old`; o `upgrade --apply` roda 1 vez por execução)
| Requisito | Teste | Tipo |
|---|---|---|
| antes: validate verde, cadeia íntegra, ≥ 30 eventos, itens nas 3 zonas, estado em `.json5` (anti-vácuo) | `TestCA05.test_ca05_alvo_realista_antes_continua` | R |
| `cs.py upgrade` (plano) sai 0 e não muda nenhum arquivo do alvo | `test_ca05_plano_nao_escreve_continua` | R |
| o plano mostra `versão do alvo:  0.10.1`, uma linha `0.11.0 — …` e cita JSON (`\bjson\b`, sem contar `json5`) | `test_ca05_plano_lista_a_migracao_de_formato` | D |
| `upgrade --apply --allow-outside` sai 0; cada `X.json5` de entidade/sessão vira `X.json` (mesmo caminho) e `X.json5` some; cada novo: JSON strict, layout do CA-01, sem chave pt, `_generated_by`, ordem; id/title/kind, ids dos critérios, `so_that` = `para` antigo e `path` = caminho `.json` preservados; histórico ≥ o antigo; `.engine/projection.json` no lugar da `.json5` | `test_ca05_apply_converte_estado_para_json_ingles` | D |
| `events.jsonl` antigo é PREFIXO byte a byte do novo; entre os eventos novos, exatamente 1 cita todo caminho antigo `.json5` de item e o seu `.json`; cadeia (seq e prev = sha256 da linha anterior, conferida por fora do motor) e validate íntegros | `test_ca05_um_evento_encadeado_novo_sem_reescrever` | D |
| 2ª `upgrade --apply` sai 0 e não muda nenhum byte em `.swarm/` (fora `backups/`, `harness-ledger.jsonl` e `.engine/evidence`); o plano seguinte não lista a 0.11.0 | `test_ca05_segunda_execucao_nao_muda_nada` | D |
| `git add -A` + `git commit` SEM `--no-verify` pelo hook do alvo passa (exit 0, HEAD anda, saída do `validate`) | `test_ca05_commit_do_resultado_passa_no_pre_commit` | D |
| um `.json5` de estado que sobrar (o texto antigo de volta no caminho antigo) é acusado pelo validate, citando o arquivo | `test_ca05_json5_orfao_e_acusado` | D |
| depois da migração o motor opera: `start US-001/01` grava `.json`, critérios corretos, nenhum `.json5` de entidade, validate verde | `test_ca05_motor_opera_depois_da_migracao` | D |

**Critérios:** o CA-05 se prova só pelo `cs.py upgrade`/`upgrade --apply` (nenhum nome de comando interno de
migração é exigido). Os testes D que dependem do apply exigem primeiro que ele tenha convertido (sem isso a
idempotência e o commit passariam no vazio). "Um evento" = um evento novo com o mapa de TODOS os caminhos; outros
eventos novos não são proibidos. O mandato M5 pode ou não mudar de formato (E1): só as chaves e valores são
conferidos (CA-06).

## CA-06 — o que não muda continua igual; versão
| Requisito | Teste | Tipo |
|---|---|---|
| `VERSION` = 0.11.0 | `TestCA06.test_ca06_version` | D |
| `references/migrations.json5`: `version` 0.11.0; a última migração é `to: "0.11.0"`, única, logo depois da 0.10.1, com ações | `test_ca06_catalogo_tem_a_0110` | D |
| catálogo continua `migrations.json5` (sem `.json`); no alvo novo `team.json5`, `run.json5`, `harness/{config,machines,routing}.json5` existem, são JSON5 legível e não ganham gêmeo `.json` | `test_ca06_catalogo_e_config_continuam_json5` | R |
| cada linha de `events.jsonl` do alvo novo continua `canonical` (`sort_keys`, separadores compactos) | `test_ca06_eventos_continuam_jsonl_canonico` | R |
| alvo novo: lição do cs-mem em `state/memory/agents/dev-billing.json5`; mandato com chaves pt (`alvo, criterios, objetivo, orcamento, regressao`) | `test_ca06_memoria_e_mandato_novos_continuam` | R |
| depois do apply: todo `*.jsonl` de antes existe e o antigo é prefixo do novo; `memory/episodes.jsonl` byte a byte igual | `test_ca06_upgrade_logs_jsonl_continuam_iguais` | R |
| depois do apply: `team.json5` byte a byte igual; config JSON5 sem gêmeo `.json`; lição do cs-mem byte a byte igual; dados do mandato MAN-001 (chaves e valores, em qualquer extensão) iguais | `test_ca06_upgrade_config_memoria_mandato_continuam` | R |

**Critério:** "logs iguais" = formato JSONL e linhas antigas intactas (anexar é permitido; reescrever não).

## Calibração (feita na escrita do oráculo, fora da suíte)
- Saída boa conhecida passa: os 15 arquivos de entidade do molde `new` convertidos por um conversor de referência
  (mapa por caminho, ordem, indent 2, `_generated_by`, `.json`) passam `assert_strict_json`, `assert_layout`,
  `assert_no_pt` e `assert_order`.
- Saída vazia/ruim reprova: `""`, `{}`, objeto sem `_generated_by`, indent 1 com `tipo`, e `history` fora do fim —
  5/5 reprovados.
- Cadeia: `chain_errors` = `[]` no alvo íntegro (43 eventos) e acusa a linha adulterada (`linha 6: prev quebrado`).
