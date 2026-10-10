# ESPEC — oráculo da campanha iter21 (memória dos agentes: B-22, B-23, B-24)

Duas camadas, escritas por quem não constrói:

- **Mecânica** — `test_iter21.py` (unittest puro, Python 3.9+, só stdlib, ~40 s por Python). CLIs reais em
  subprocesso (`cs.py`, `.swarm/harness/{state,mem,guard,validate}.py` instalados no alvo), hook git real, repos git
  temporários. Placar por requisito: `python3 medir.py`. Base em `base.txt`.
- **Comportamental** — `prova_real.py` roda o Claude Code de verdade (`claude -p`). O oráculo só traz `--dry-run` e
  `--offline-check`. Quem roda a prova com API é o tech-lead, depois de congelar.

Skill sob teste: `$CS_SKILL_DIR` (padrão: a raiz do projeto). Skill antiga (M6): `$CS_OLD_SKILL_DIR`, ou então
`git archive 97a1718` (0.10.1). Temporários ficam em `$CS_ORACLE_TMP` (padrão: o tempdir do Python). Com
`CS_ORACLE_KEEP=1` os temporários não são apagados.

Legenda: **D** = defeito (falha na base, passa depois da correção). **R** = não-regressão ou controle (passa antes e
depois). O `medir.py` classifica como R os testes cujo nome contém `regressao|controle|continua|intacta`.

## Problema (uso real, harness 0.10.1, segunda cobaia .NET)
- **B-22.** O emit declara `memory: project` nos cartões, mas o guard reserva `.claude/` e ninguém escreve
  `.claude/agent-memory/<agente>/MEMORY.md`. A correção do dono (/correct → cs-mem) não chega ao agente de forma
  garantida no próximo despacho.
- **B-23.** O brief despeja o glossário do território em ordem alfabética, e as linhas "leia as referências" e "fora
  de escopo" saem vazias.
- **B-24.** `cs-mem search` não deixa rastro, então não dá para medir se o agente pesquisa.

Fato da plataforma (documentação oficial do Claude Code): com `memory: project`, as primeiras 200 linhas ou 25 KB
do `MEMORY.md` entram no system prompt do subagente a cada despacho. Isso só existe no Claude Code. Em
Cursor/Copilot/Codex o canal é o brief.

## Dados de uso real que o tech-lead mandou (DADO, não escopo)
1. O caderno feito à mão foi injetado: o agente citou o caderno literalmente. A instrução de pesquisa que estava só no
   caderno NÃO mudou o comportamento ("tratei a tarefa como trivial"). O `consultei:` funcionou como auditoria.
2. Depois que o caderno passou a dizer "Pesquisa obrigatória no cs-mem (o gate confere) ANTES da 1ª edição quando a
   task toca <gatilho>", o agente pesquisou antes de editar e o gate conferiu (n=1, com gatilho explícito).
3. O formato de prova que não se inventa é `consultei: "TEMA" -> ID (efeito)`, com o ID impresso pela busca. O gate
   reexecuta ou consulta o rastro.
4. Requisito do dono para o /correct: classificar de quem é o erro (o brief mandou X e o agente fez X ⇒ a lição é do
   lead; o brief mandou X e o agente fez Y ⇒ a lição é do agente e vai para o caderno dele).
5. Caminho único: a escrita é sempre cs-mem → caderno. Lição escrita só no MEMORY.md não vale como correção.

## Fixture
- **Domínio inventado (estufa/cultivo)**, sem nada da cobaia. O time tem `dev-cultivo` (`src/cultivo/**`),
  `dev-painel` (`src/painel/**`), `reviewer` (gate) e `qa` (`tests/**`). A armadilha do cartão de dev-cultivo é
  "Dose de calcário lançada em quilos zerou a correção do solo". São 30 termos de glossário no formato do scan L9
  (`facts` com `id: gloss.<slug>` e `scope: [src/cultivo/**]`, mais `terms` para o emit). O termo relevante da task
  do M7 (`gloss.vernalizacao`) é o último em ordem alfabética.
- **Alvo novo:** `cs.py init --platforms claude-code` + `harness install` + `emit` + `cs-state init`, tudo commitado.
  Depois o pre-commit é ligado com `harness install --git-hook`. A sonda confere que o hook barra
  `src/painel/app.py`. Todo commit do teste usa `-c core.hooksPath=<alvo>/.git/hooks`. A fixture desliga
  `gc.auto`, `gc.autoDetach` e `maintenance.auto`: sem isso, um gc do git em segundo plano quebrava a cópia do molde
  (achado da medição, falha intermitente no alvo multiplataforma).
- **Alvo multi:** a mesma coisa com `--platforms cursor,copilot,codex`, sem hook.
- **Alvo 0.10.1:** o mesmo domínio gerado pela skill 0.10.1 real (`git archive 97a1718`).
- **Task em voo:** `cs-state new task --avulsa` → `start` → `dispatch --manual --model sonnet` (como os oráculos
  iter18 e iter19).
- **Guard:** `.swarm/harness/guard.py <modo>` com o payload oficial dos hooks (`tool_name`, `tool_input`,
  `agent_id`/`agent_type` para o subagente; sem `agent_id` = orquestrador) e `CLAUDE_PROJECT_DIR` = o alvo.

## Marcadores do bloco (critério)
O bloco é o trecho entre as duas primeiras linhas que casam com `<!--[^\n]*cs-mem[^\n]*-->`. Qualquer par serve, por
exemplo `<!-- cs-mem:inicio -->` … `<!-- cs-mem:fim -->`. O oráculo exige que o marcador inicial esteja nas 3
primeiras linhas (o bloco fica "no topo") e que o token `cs-mem…` do marcador apareça, junto com "MEMORY.md", em algum
`docs/*.md` ou `references/*.md` da skill ("desde que documentado"). Seções reconhecidas pelo título markdown
normalizado (sem acento, minúsculas): `correcoes recebidas`, `armadilhas do territorio`, `quando pesquisar`.

## Placar da base (HEAD 73a492e, VERSION 0.10.1; iguais em python3 3.13.3 e /usr/bin/python3 3.9.6)

| req | D (passam/total) | R (passam/total) | total |
|---|---|---|---|
| M1 caderno gerado pelo cs-mem | 0/4 | 1/1 | 1/5 |
| M2 regeneração, área livre, caminho único | 0/6 | — | 0/6 |
| M3 cabe nas 200 linhas / 25 KB | 0/1 | — | 0/1 |
| M4 guard do caderno | 0/2 | 6/6 | 6/8 |
| M5 pre-commit do caderno | 0/1 | 2/2 | 2/3 |
| M6 emit/install/upgrade preservam; upgrade 0.10.1 gera | 0/2 | — | 0/2 |
| M7 brief relevante | 0/2 | 3/3 | 3/5 |
| M8 outras plataformas: brief é o canal | — | 2/2 | 2/2 |
| M9 rastro da pesquisa (B-24) | 0/4 | 1/1 | 1/5 |
| M10 `consultei:` conferido; ausência visível ao gate | 0/4 | 3/3 | 3/7 |
| M11 /correct classifica quem errou | 0/3 | — | 0/3 |
| M12 refinar/retratar lição; /correct confirma antes | 0/4 | 1/1 | 1/5 |
| M13 memória sob orçamento; `cs-mem check` documentado; ordem (mudança oficial 1) | 0/3 | — | 0/3 |
| **total** | **0/36** | **19/19** | **19/55** |

## M1 — o cs-mem gera o caderno (B-22, D)
| Requisito | Teste | Tipo |
|---|---|---|
| `cs-mem correct --agent dev-cultivo …` cria `.claude/agent-memory/dev-cultivo/MEMORY.md` com o bloco no topo e a correção nele | `TestM1CadernoGerado.test_m1_correct_gera_caderno_com_bloco_no_topo` | D |
| `cs-mem add --agent … --kind lesson` também gera | `test_m1_add_licao_gera_caderno` | D |
| bloco com as 3 seções; Correções contém a correção; Armadilhas contém a armadilha do cartão; Quando pesquisar tem `cs-mem search` e ≥ 1 termo do território (do scan) | `test_m1_secoes_do_bloco` | D |
| o token do marcador e "MEMORY.md" documentados em docs/ ou references/ | `test_m1_marcadores_documentados` | D |
| alvo sem lição não tem correção inventada no bloco (anti-vácuo) | `test_m1_sem_correcao_nao_ha_vacuo_controle` | R |

## M2 — regeneração e caminho único (D)
| Requisito | Teste | Tipo |
|---|---|---|
| 2ª correção regenera o bloco com as duas; a área livre abaixo do bloco sobrevive, sem duplicar | `TestM2Regeneracao.test_m2_correct_regenera_e_preserva_area_livre` | D |
| um MEMORY.md que já tinha notas (sem bloco) ganha o bloco e mantém as notas fora dele | `test_m2_notas_anteriores_ao_primeiro_bloco_preservadas` | D |
| lição arquivada por decaimento (`cs-mem archive` depois de envelhecer `first_seen`/`last_hit` no arquivo de lições) sai do bloco | `test_m2_decaimento_tira_licao_do_bloco` | D |
| lição de dev-cultivo não regrava o caderno de dev-painel (bytes iguais) | `test_m2_outro_agente_intacto` | D |
| `archive` sem mudança não muda bytes | `test_m2_regenerar_sem_mudanca_mesmos_bytes` | D |
| linha posta à mão dentro do bloco some na regeneração; "lição" escrita só na área livre não entra no bloco nem nas lições do cs-mem | `test_m2_bloco_derivado_so_do_cs_mem` | D |

**Critério (decaimento):** o teste envelhece a lição editando o arquivo de lições em `.swarm/state/memory/agents/`.
Isso simula a passagem de 60 dias, porque o motor não tem relógio injetável. Não é um caminho de uso.

## M3 — cabe no que a plataforma injeta (D)
| Requisito | Teste | Tipo |
|---|---|---|
| 34 correções longas e distintas (o teto deixa 29 ativas) e 30 termos: o marcador final fica antes da linha 200, o bloco tem ≤ 25 KB e a correção mais recente está nele | `TestM3Limite.test_m3_bloco_cabe_200_linhas_25kb` | D |

## M4 — guard do caderno
| Requisito | Teste | Tipo |
|---|---|---|
| subagente (delegação DISPATCHED) edita a área livre do PRÓPRIO caderno (Edit) → liberado; o post-edit não reverte | `TestM4Guard.test_m4_subagente_edit_na_area_livre_liberado` | D |
| Write do próprio caderno com o bloco intacto → liberado | `test_m4_subagente_write_preservando_bloco_liberado` | D |
| subagente edita o bloco (Edit) → recusado OU restaurado | `test_m4_subagente_edita_o_bloco_continua_protegido` | R |
| subagente reescreve com o bloco adulterado (Write) → recusado OU restaurado | `test_m4_subagente_write_com_bloco_adulterado_continua_protegido` | R |
| dev-painel escreve no caderno de dev-cultivo (Write/Edit) → recusado | `test_m4_outro_agente_nao_escreve_caderno_alheio_continua` | R |
| idem por Bash (`echo … >> …/MEMORY.md`) → recusado | `test_m4_outro_agente_bash_no_caderno_alheio_continua` | R |
| orquestrador reescreve o bloco → recusado OU restaurado | `test_m4_orquestrador_nao_escreve_o_bloco_continua` | R |
| durante a delegação, o agente anota no caderno e o cs-mem o regenera: `cs-state verify` continua verde | `test_m4_verify_nao_conta_o_caderno_do_agente_continua` | R |

**Critério "recusado ou restaurado":** passa se o `pre-write` sai com 2. Se ele liberar, o teste aplica a escrita,
roda `post-edit` (e, se ainda não restaurou, `subagent-stop` para subagente ou `stop` para o orquestrador) e exige o
bloco byte a byte igual ao que o cs-mem gerou. Hoje esses testes passam porque o guard recusa qualquer escrita em
`.claude/agent-memory/` (R). Eles barram a correção preguiçosa "libera o caderno inteiro". Para o outro agente, só a
recusa vale.
**Achado (R, não D):** o verify da 0.10.1 já não reprova por arquivo em `.claude/agent-memory/` (conferido na base).

## M5 — pre-commit do caderno
| Requisito | Teste | Tipo |
|---|---|---|
| depois de `cs-mem correct` + nota na área livre, `git add -A` + commit SEM --no-verify passa (o hook rodou: `validate` na saída); um 2º commit só com a área livre mudada também passa | `TestM5PreCommit.test_m5_commit_do_caderno_passa_sem_no_verify` | D |
| bloco adulterado → barrado, citando o caderno | `test_m5_bloco_adulterado_continua_barrado` | R |
| bloco removido → barrado, citando o caderno | `test_m5_bloco_removido_continua_barrado` | R |

Os R passam hoje porque o caderno inteiro fica fora de qualquer allowed_paths. Quando não há caderno gerado, eles
criam um bloco sintético. Junto com o D, impedem a saída "libera `.claude/agent-memory/**`".

## M6 — sobrevive a emit/install/upgrade; o upgrade gera o caderno (D)
| Requisito | Teste | Tipo |
|---|---|---|
| `emit`, `harness install` e `upgrade --apply` (sem migração pendente) não apagam nem mudam um byte do caderno (bloco + área livre) | `TestM6Sobrevive.test_m6_emit_install_upgrade_nao_mudam_o_caderno` | D |
| alvo 0.10.1 REAL com lição registrada pela 0.10.1: `upgrade --apply` gera o caderno com a lição e o commit do resultado passa sem --no-verify | `TestM6UpgradeDe0101.test_m6_upgrade_gera_caderno_de_licao_existente_e_commita` | D |

**Critério:** o número da versão nova não é testado, porque a iter19 (0.11.0) está aberta e a ordem de entrega é
decisão do tech-lead. Exige-se só o efeito da migração.

## M7 — brief relevante (B-23)
Task: título "Ajustar a vernalização das sementes", goal "a vernalização precisa durar seis semanas",
`allowed_paths: src/cultivo/vernalizacao.py`. Os 30 termos têm o mesmo escopo, então só o texto discrimina.

| Requisito | Teste | Tipo |
|---|---|---|
| o termo relevante está no brief, no máximo 8 dos 29 termos sem relação aparecem, e nenhum deles antes do relevante | `TestM7Brief.test_m7_termo_relevante_primeiro_sem_dump` | D |
| nenhum rótulo "referências"/"fora de escopo" termina vazio (preencher ou omitir) | `test_m7_rotulos_referencias_e_fora_de_escopo_nao_vazios` | D |
| o brief já traz o resultado da busca na memória (decisão do dono registrada no cs-mem aparece sem o agente pesquisar) | `test_m7_brief_traz_resultado_da_busca_controle` | R |
| a lição relevante do agente está no brief | `test_m7_licao_relevante_no_brief_controle` | R |
| título, allowed_paths e AC continuam no brief | `test_m7_task_titulo_escopo_aceite_continua` | R |

**Achado da base:** o brief lista os 30 termos de A a Z ("29 termos sem relação"), e a seção MEMÓRIA trouxe termos
sem relação (hidroponia, sombrite, xaxim) para a task "Ajustar etapa". "Omitido com motivo" não é testável sem
amarrar o texto. O oráculo aceita a linha ausente ou preenchida.

## M8 — outras plataformas (R)
| Requisito | Teste | Tipo |
|---|---|---|
| alvo `cursor,copilot,codex`: a lição registrada pelo cs-mem chega pelo brief (`cs-state brief`); MEMORY.md não é exigido | `TestM8OutrasPlataformas.test_m8_brief_e_o_canal_da_licao_controle` | R |
| o cartão claude-code continua com `memory: project` | `TestM8CartaoClaude.test_m8_cartao_declara_memory_project_continua` | R |

## M9 — rastro da pesquisa (B-24, D)
| Requisito | Teste | Tipo |
|---|---|---|
| `cs-mem search "<q>" --agent dev-cultivo --json` grava uma linha JSON sob `.swarm/` (fora de `memory/index/` e `harness/`) que contém o agente, a consulta e um inteiro igual ao nº de resultados | `TestM9Rastro.test_m9_search_registra_agente_consulta_hits` | D |
| consulta com 0 resultados registrada com 0 | `test_m9_zero_hits_registrado` | D |
| a saída texto (sem --json) também registra | `test_m9_saida_texto_tambem_registra` | D |
| append-only: depois de outra busca, o arquivo começa com os bytes anteriores | `test_m9_append_only` | D |
| a busca continua devolvendo resultados | `test_m9_busca_continua_respondendo_controle` | R |

**Critério:** o oráculo não fixa o nome do arquivo nem das chaves. Ele exige JSONL (como ledger, events e episodes) e
os três valores. O agente é passado com `--agent`. Atribuir o agente sem `--agent` (por exemplo pelo hook) é a critério
do corretor, e a prova real mede isso.

## M10 — `consultei:` conferido contra o rastro; ausência aceita, mas visível ao gate
Canal: `--handoff-notes` do `cs-state submit` (o campo livre que já existe e que todas as plataformas usam). Formato do
dono: `consultei: "TEMA" -> ID (efeito)` ou `consultei: nada — <motivo>`.

| Requisito | Teste | Tipo |
|---|---|---|
| consulta feita (`cs-mem search … --agent`), ID tirado do resultado → submit e verify passam | `TestM10Consultei.test_m10_consulta_real_aceita_controle` | R |
| `consultei: nada — motivo` → passa | `test_m10_consultei_nada_aceito_controle` | R |
| declaração feita não aparece como "não declarado" na visão do gate | `test_m10_declarado_nao_aparece_como_nao_declarado_controle` | R |
| consulta citada que nunca foi feita → submit OU verify recusa, citando consulta/consultei | `test_m10_consulta_inexistente_no_rastro_recusada` | D |
| consulta feita, mas o ID citado não sai dela (reexecutada ou registrada) → recusa | `test_m10_id_que_nao_saiu_da_busca_recusado` | D |
| submit SEM `consultei:` é ACEITO (rc 0), mas o gate vê "consultei: não declarado" | `test_m10_submit_sem_consultei_aceito_e_registrado_nao_declarado` | D |
| o brief de implementação mostra o formato `consultei:` | `test_m10_brief_ensina_consultei` | D |

**Decisão do tech-lead (substitui a colisão da versão anterior):** `consultei:` NÃO é obrigatório para o submit passar.
Assim os oráculos congelados iter10, iter13, iter16, iter18, iter19 e m5, que submetem com `--handoff-notes ok`,
continuam válidos. O efeito observável exigido é que a ausência fique registrada de forma visível ao gate. A visão do
gate, para o oráculo, é a junção de: a saída de `cs-state verify <task>`, a de `cs-state why <task>`, o brief de
revisão (`cs-state brief <task> --phase review --agent reviewer`) e os arquivos de estado sob `.swarm/` cujo nome
contém o id da task. Alguma linha precisa conter "consultei" e "não declarad" ou "sem declaraç" (sem acento,
minúsculas). O nome do campo é livre.
**Não coberto:** a coerência do "(efeito)" com o diff fica para o revisor e para a prova real, porque não é
mecânica sem amarrar o formato do efeito.

## M11 — /correct classifica quem errou (D)
Contrato mínimo (o único nome de interface que o oráculo fixa): `cs-mem correct … --fault brief|agent`.

| Requisito | Teste | Tipo |
|---|---|---|
| `--fault brief` → a lição vai para o `lead` com `source: brief`, não fica no dev-cultivo e não entra no caderno dele | `TestM11QuemErrou.test_m11_erro_do_brief_vai_para_o_lead` | D |
| `--fault agent` → a lição fica no dev-cultivo e entra no bloco do caderno | `test_m11_erro_do_agente_vai_para_o_caderno` | D |
| a skill `/correct` gerada no alvo cita `--fault` e "brief" (pergunta ou classifica) | `test_m11_correct_skill_pergunta_quem_errou` | D |

O nome `--fault` é uma decisão do oráculo, que segue os flags em inglês do cs-mem (`--wrong/--right/--why`). Trocar o
nome é `oracle change`. Os testes M1–M10 chamam `correct` SEM `--fault`. Se o corretor tornar o flag obrigatório,
precisa manter um padrão retrocompatível ou fazer `oracle change`. A prova real detecta o flag no `--help`.

## M12 — refinar ou retratar uma lição; /correct confirma antes de gravar
Caso de uso real: a regra virou lição em 2 agentes e o dono a refinou logo depois. Na 0.10.1, `cs-mem correct` só
cria lição nova, e as duas ficam `active`, injetadas juntas e contraditórias.
Contrato mínimo (os nomes de interface que o oráculo fixa, como o `--fault`): `cs-mem correct … --supersedes <id>` e
`cs-mem retract <id> --reason "<motivo>"`. O id é o que o `correct` imprime no JSON de saída.

| Requisito | Teste | Tipo |
|---|---|---|
| a mesma regra em dev-cultivo e em dev-painel; `correct --supersedes <id>` em cada um → evento JSONL novo sob `.swarm/` citando o id antigo; o antigo deixa de ser `active`, sai do brief, do `cs-mem inject`, do bloco do caderno e da busca como ativo; a refinada fica active, no brief e no bloco | `TestM12Refinamento.test_m12_supersede_em_dois_agentes` | D |
| `retract <id> --reason` → evento JSONL com o id e o motivo; mesma exclusão de injeção | `test_m12_retract_com_motivo` | D |
| `retract <id>` sem motivo → recusado pedindo o motivo (não "comando desconhecido"); a lição continua active | `test_m12_retract_sem_motivo_recusado` | D |
| lição nova (correct comum) continua active e injetada no brief e no inject | `test_m12_licao_nova_ativa_e_injetada_controle` | R |
| a skill /correct gerada mostra errado/certo/porquê e pede confirmação ANTES do `cs-mem correct`; se o `correct --help` tiver um modo de prévia (`--dry-run`, `--preview` ou `--plan`), ele mostra a lição e não grava nada | `test_m12_correct_mostra_e_confirma_antes_de_gravar` | D |

"Evento na cadeia ou no ledger": o oráculo exige texto novo, anexado a algum `.jsonl` sob `.swarm/` (fora do índice e
do motor), que cite o id. O arquivo é livre.
**Critério (confirmação na CLI):** os testes M1–M11 chamam `correct` sem confirmação. A confirmação é exigida na
skill (o humano), não na CLI. Se o corretor tornar a confirmação obrigatória na CLI, precisa de `oracle change`.

## M13 — a memória chega sob orçamento; o `cs-mem check` documentado funciona (mudança oficial 1, D)
Dado de uso real (segunda cobaia .NET, despacho real, qa com 2 lições ativas em tests/**):
- (A) o `package()` do brief emite as seções por prioridade até `context_budget_chars` (10 000). "TERMOS DO ESCOPO",
  que é o dump do glossário, consome o orçamento, e "MEMÓRIA", que traz as lições e o resultado da busca, sai INTEIRA
  ("+38 itens omitidos pelo orçamento").
- (B) `cs-mem check --agent X` sem `--files` sai sempre vazio, e é esse o comando que o cartão e o brief mandam rodar.
- (C) no empate de count, a lição antiga vem antes da nova.

Fixture nova: o alvo `big` é o domínio com mais 400 termos sintéticos (`Q…x###`, sem nenhuma palavra das tasks) no
mesmo território, sem hook.

| Requisito | Teste | Tipo |
|---|---|---|
| alvo `big`, task do M7: a lição relevante (`correct`) e a decisão do dono no cs-mem continuam no brief, e no máximo 8 termos sem relação (dos 429) aparecem | `TestM13BriefSobOrcamento.test_m13_licao_e_busca_sobrevivem_ao_orcamento` | D |
| delegação qa DISPATCHED com diff em `tests/test_ok.py` e lição com trigger `tests/**`: o comando `cs-mem check` copiado do cartão emitido E do brief (texto do artefato, sem placeholder `<…>`) devolve a lição | `TestM13CheckDocumentado.test_m13_check_documentado_devolve_licao_da_delegacao` | D |
| duas lições ativas, de mesmo count e sem palavra em comum (o dedup funde lições parecidas), com a antiga de menor id: `check --files` lista a mais recente primeiro | `test_m13_check_empate_mais_recente_primeiro` | D |

**Calibração (M13):** no alvo `big` com `context_budget_chars` aumentado à mão para 400 000, a lição aparece no brief.
Isso prova que a asserção mede o corte por orçamento. Mas os 400 termos aparecem, então "só aumentar o orçamento"
continua reprovando pelo dump. `check --files tests/test_ok.py` devolve a lição hoje, o que confirma que o defeito B
está no comando documentado (`.swarm/bin/cs-mem check --agent qa`, no cartão e no brief). Na 1ª versão do teste C,
textos parecidos foram fundidos pelo dedup e promovidos, e o teste falhava pelo motivo errado. A fixture agora confere
que há 2 lições ativas e que a antiga tem o menor id.
**M7:** fica como está. O `test_m7_licao_relevante_no_brief_controle` continua R no alvo pequeno (30 termos, sem estouro).
A condição sob orçamento estourado é o M13.

## Compatibilidade com os oráculos congelados (conferido por leitura)
- **iter18** (TestR1..R7): os testes não usam cs-mem, caderno, termos do brief nem `consultei:`. O submit
  `--handoff-notes ok` continua aceito pelo novo M10. O `glossary.json5 = []` da fixture deles não tem termo, então
  o M7 não o afeta.
- **iter19:** `populate()` faz `cs-mem add --agent dev-billing --rule …` e depois `commit_all` com o hook. Com a
  iter21, isso gera `.claude/agent-memory/dev-billing/MEMORY.md`, que precisa passar no pre-commit: é o que o M5 exige.
  No caminho 0.10.1 → 0.11.0, o M6 faz o upgrade gerar o caderno da lição existente. O
  `test_ca05_segunda_execucao_nao_muda_nada` só compara `.swarm/`. O `test_ca05_commit_do_resultado_passa_no_pre_commit`
  exige o commit do resultado, coberto por M5 e M6. O `test_ca06_upgrade_config_memoria_mandato_continuam` exige os
  bytes de `state/memory/agents/dev-billing.json5` iguais: o upgrade não pode reescrever o arquivo de lições ao gerar
  o caderno. O iter21 não pede essa reescrita, mas o corretor deve respeitar isso. O brief (`test_ca02`/`ca03`) é
  conferido só por critério e caminho, que o M7 mantém (R `test_m7_task_titulo_escopo_aceite_continua`).
- **iter20:** os testes não usam cs-mem. O upgrade, o emit e o install passam a poder escrever o caderno. O M6 exige
  que, sem lição nova, nada no caderno mude, e os U1–U4 continuam valendo para o resto.

## Prova real — `prova_real.py` (camada comportamental, roda o Claude Code)
Convenção do dono que contraria a intuição: em `src/cultivo/dependencias.py`, `DEPENDE_DE` é indexado pelo
PRÉ-REQUISITO. "A depende de B" vira `DEPENDE_DE["b"]` contendo `"a"` (X, certo). Pelo nome, o óbvio é
`DEPENDE_DE["a"]` contendo `"b"` (Y, errado). O repositório não revela a convenção: as duas entradas existentes são
ambíguas. A medida é mecânica (`ast.literal_eval` do dicionário): X, Y, AMBOS, INALTERADO ou ERRO.

| P | Cenário/config | O que mede | Despachos (N=3) |
|---|---|---|---|
| P1 | `base` (sem lição; V0, V1, V2) | taxa X antes da correção (esperado: baixa) | 3 |
| P2 | correção pelo caminho do produto: `cs-mem correct` (o que o `/correct` gerado roda; com `--fault agent` se existir), sem editar MEMORY.md | caderno gerado? (`caderno depois da correção`) | 0 |
| P3 | `depois` (sessão nova; V1–V3, nunca a frase da correção) | (i) entrega, **(ii) aplicação**, (iii) detecção | 3 |
| P4 | `sem-gatilho` (título neutro, frase sem "depende/grafo"; o gatilho vem só do caminho) | idem, sem o caso fácil | 3 |
| P5 | `persistencia` (2 tasks sem relação despachadas, `cs.py emit`, `cs.py upgrade --apply`, sessão nova) | idem | 3 + 2 |
| P6 | `sem-caderno` (mesma lição no cs-mem; `memory: project` tirado do cartão e caderno apagado) | valor do caderno = depois − sem-caderno (L04/L12) | 3 |
| P7 | `pesquisa` (termo "Calagem" fora do cartão; o valor 180 só existe numa decisão no cs-mem) | pesquisou DE FATO × declarou, coerência e valor certo | 3 |
| P8 | `refinamento` (OPCIONAL, só com `--configs` explícito; diagnóstico, fora do critério de parada): depois da CV-7, o dono refina para a CV-8 (chave = pré-requisito e nomes em MAIÚSCULAS) por `correct --supersedes` (se existir) | aplica a REFINADA (`DEPENDE_DE['IRRIGACAO']` ⊇ `'DRENAGEM'`…); `antiga_injetada` = a CV-7 ainda chegou (brief ou bloco), ou seja, contradição | 3 |

Por execução e agregado por cenário/config, com medidas SEPARADAS:
- **(i) ENTREGA:** `canal_caderno` (o bloco do MEMORY.md tem o token `CV-7` antes do despacho), `canal_brief` (o brief
  que o SubagentStart injeta tem o token) e `citou` (a saída do subagente cita o token).
- **(ii) APLICAÇÃO espontânea:** classe X sem que o prompt cobre a convenção. O offline-check garante que nenhum prompt
  cita "pré-requisito", "convenção" ou `CV-7`, e que as variantes sem gatilho não citam "depende/grafo".
- **(iii) DETECÇÃO:** quando não aplicou, `cs-state verify`, `cs-mem check` e `validate` rodam depois da execução.
  "Acusou" = rc≠0 citando a lição ou a consulta.
- **Pesquisa:** "pesquisou de fato" = no transcript do subagente (stream-json, `tool_use` em ordem, com
  `parent_tool_use_id`) há uma `cs-mem search` ANTES da 1ª edição de produto. A edição do próprio caderno não conta.
  Se o stream não trouxer o subagente, a fonte é o `obs.jsonl` (hook PostToolUse da prova, em
  `.claude/settings.local.json` da cópia). "Declarou" = `consultei:` na submissão ou nos comandos. "Coerente" = o
  tema está no rastro B-24 e o ID está no `tool_result` da busca. O placar cruza pesquisou∧declarou, declarou sem
  pesquisar e pesquisou sem declarar. O rastro B-24 entra só como diagnóstico.

**Critério de parada da campanha:** APLICAÇÃO (ii) ≥ 80% em `depois`, `sem-gatilho` e `persistencia`. (i) e (iii)
são diagnóstico e também entram no placar. Saída: `placar.json` (`{cenario, config, n, x_aplicado, taxa, entregue,
citou, nao_aplicou, detectado, pesquisou, declarou, …, custo_usd}`) e `resumo.md`. Cada execução fica em
`<out>/<config>/<rep>/` com `alvo/`, `prompt.txt`, `brief.txt`, `saida.jsonl`, `stderr.txt`, `obs.jsonl`,
`caderno-antes.md`/`caderno-depois.md`, `dependencias.py`, `resultado.json` e `notes.md`.

Isolamento: `--out` é obrigatório e não pode ter ancestral abaixo de `$HOME` com `CLAUDE.md`,
`.claude/CLAUDE.md` ou `.claude/settings*.json`, porque o Claude Code carrega CLAUDE.md dos diretórios pai. Por isso
`local/` deste projeto NÃO serve. Cada execução é uma cópia nova do molde e um `claude -p` novo com
`--no-session-persistence`, `--setting-sources project,local` (sem plugins/hooks do usuário), `--strict-mcp-config`,
`--permission-mode acceptEdits --permission-prompts none` e `--allowedTools` restrito, com stdin em /dev/null. Com
N=3: **20 despachos** (pior caso 300 min com timeout de 900 s). Com o refinamento: 23.
**Mudança oficial 1:**
- O molde da prova usa o glossário na ESCALA REAL (`--termos`, padrão 400 a mais, 430 no total). O brief estoura o
  orçamento como no alvo real, e o `sem-caderno` mede o agente sem caderno pelo canal brief/check que o M13 corrige.
- A allow-list ganha `Bash(python3 *)`, `Bash(echo *)`, `git status|diff|log|show` e os binários `cs-state`/`cs-mem`
  pelo caminho absoluto do alvo. Nunca bypass.
- O parser tolera `message` string e linhas inesperadas.
- Cada despacho grava `negacoes.json`, com a origem `permissao` (allow-list) ou `produto` (hook, como o cs-guard).
- Um despacho que quebra vira NOT_RUN (fora do n) sem derrubar a rodada.
- A rodada ABORTA se o 1º despacho tiver Bash negado pela allow-list.
- `--offline-check --sonda-api` (`--sonda-model haiku`, `--sonda-budget 0.2`) faz 1 despacho real que confirma que o
  subagente roda `cs-mem search`, `python3 …; echo …` e `git status` no alvo.
**stream-json conferido:** uma sonda de 1 chamada (`claude -p`, haiku, US$ 0,15, agente inline `eco` rodando
`echo`) mostrou o `tool_use` Bash e o `tool_result` do subagente com `parent_tool_use_id` preenchido, em ordem. O
Agent foi lançado de forma ASSÍNCRONA, e o stream trouxe dois `result`. O custo é a soma deles. O `tool_events()` e o
`search_order()` da prova leem esse stream real corretamente (fonte "transcript").

## Calibração
- **Formato (M1/M3):** um conversor de referência no scratch (lições ativas do cs-mem + armadilhas do cartão + 20
  termos → bloco `<!-- cs-mem:inicio … -->`/`<!-- cs-mem:fim -->` + área livre) passa nas mesmas asserções com 34
  correções reais registradas (bloco de 59 linhas e 12 302 bytes; a mais recente presente; 29 itens = 29 ativas no
  cs-mem). REPROVAM: vazio, sem marcador, sem uma seção, bloco no fim (depois de 5 linhas) e bloco estourado (258
  linhas).
- **Medida X/Y da prova:** o offline-check classifica X, Y, AMBOS, INALTERADO, arquivo vazio (ERRO) e sintaxe quebrada
  (ERRO) corretamente. A saída vazia reprova.
- **Pesquisa da prova:** transcript sintético no formato stream-json. Busca antes da edição + ID do resultado =
  coerente. Busca depois da edição NÃO conta. ID inventado NÃO é coerente. Declarar sem pesquisar NÃO é coerente.
  `consultei: nada` = declarou sem consulta.
- **Conferido à mão:** (1) o brief da base lista os 30 termos de A a Z (saída de `cs-state brief` lida). (2) O guard
  recusa o subagente no próprio caderno com "fora de allowed_paths" e o orquestrador com "não escreve produto" (sonda
  manual, rc=2). (3) Sem `--founder` ou evidência, o `cs-mem add --kind decision` sai com rc 1 ("entrada sem
  evidência"). O teste M7 passa `--founder Ana`.

## Fora do escopo do oráculo
- O formato interno do bloco além dos marcadores e títulos; onde mora o rastro; o nome das chaves do JSONL.
- O conteúdo exato de "Quando pesquisar" (exige-se o comando e ≥ 1 termo do território). A palavra "obrigatória" e o
  gatilho explícito do piloto 2 são medidos pela prova real (P4/P7), não por texto.
- A coerência "(efeito)" × diff no `consultei:`.
