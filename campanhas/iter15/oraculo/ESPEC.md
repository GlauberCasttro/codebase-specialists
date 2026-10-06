# ESPEC — oráculo campanha-iter15 (nomes em inglês, migração 0.9.0, guia gerado, corte de invariantes no S2)

Oráculo: `test_iter15.py`, com 28 testes em unittest puro (Python 3.9+), alvos em `tempfile`. Base: `base.txt`. Contra a
skill viva, nos dois Pythons (3.13.3 e 3.9.6): **19 falham e 9 passam**. Dos 9 que passam, 5 são do R4, porque o diff
não commitado do `render.py` já está na árvore. Os outros 4 são regressão ou pré-condição (lista no §4). Quem
implementa **não edita** o oráculo. Mudança em teste congelado vai para `mudanca-oficial/`, com patch e `PORQUE.md`.

Como o oráculo observa: `cs.py` e `scripts/emit/cli.py` rodam em subprocesso, com o caminho real de geração e de
upgrade. Não há mock. A skill sob teste é `$CS_SKILL_DIR`; sem ele, `~/.claude/skills/codebase-specialists`. A
**skill 0.8.x de referência** é extraída por `git archive` de `$CS_SKILLS_REPO` (padrão `~/.claude/skills`), no
commit `$CS_OLD_REF`. Sem `CS_OLD_REF`, vale o commit mais recente que toca `codebase-specialists/` e tem VERSION
`0.8.*`, que hoje é o HEAD. Para rodar, de dentro desta pasta: `python3 -m unittest -v test_iter15`, e depois o mesmo
com `/usr/bin/python3`.

Leva cerca de 8 s por Python. O oráculo não depende do conteúdo das partes que a iter14 mexe (`engine/{auto,guard,senha}.py`,
`install.py`, `auto-approve.md`, `docs/11`). Ele compara a skill nova com a 0.8.x **pelo que o emit gera**, não pelo
texto dessas partes.

## 1. Requisito → testes

| Req | O que se prova | Testes |
|---|---|---|
| R1 (a) INIT | Projeto novo pelo caminho real (`cs.py init --platforms claude-code,cursor,copilot,codex` → `cs.py harness install --allow-outside --git-hook` → `cs.py emit --allow-outside`). Em **cada** plataforma, toda skill que a 0.8.x gerava aparece com o nome novo (mapa do §2.1), nenhuma com nome antigo, e `name:` = nome da pasta | `TestR1InitProjetoNovo.test_cada_plataforma_tem_os_nomes_novos_no_lugar_dos_antigos` |
| R1 (a) só o nome muda | Cada renomeada mantém, em relação à 0.8.x e na mesma plataforma: `disable-model-invocation`, `argument-hint`, `allowed-tools` e `arguments` iguais; o texto "só o humano executa" (Codex) igual; os comandos `.swarm/bin/cs-x <sub>` citados no corpo, pelo menos os mesmos | `test_renomeadas_mantem_politica_argumento_e_comando` |
| R1 (a) nenhum nome antigo | Varre **todo** o projeto gerado, exceto `.git`: nenhum arquivo cita um nome antigo como nome de skill ou comando (regex do §2.2), e nenhuma pasta gerada tem nome antigo | `test_nenhum_nome_antigo_em_nenhum_arquivo_gerado` |
| R1 (a) núcleo/kernel | `CLAUDE.md` cita `/save-session`, `/load-session`, `/correct` e `/plan-sprint`; `.claude/orchestrator.md` cita `/correct` | `test_claude_md_e_orchestrator_citam_os_novos` |
| R1 (a) G7 | `cs.py emit validate` verde no projeto novo | `test_emit_validate_verde` (já passa hoje) |
| R1 fontes | Nenhum nome antigo em `SKILL.md`, `MODO-DE-USO.md`, `assets/templates/**`, `references/**`, `docs/**` e `scripts/**` (fora de `tests/`), salvo as exceções do §2.3 | `TestR1FontesDaSkill.test_nenhum_nome_antigo_em_template_doc_guia_ou_codigo` |
| R2 (b) pré-condição | O alvo montado pela 0.8.x tem as 6 antigas no manifesto do emit | `TestR2UpgradeDe08.test_precondicao_alvo_08_tem_as_antigas_no_manifesto` (já passa hoje) |
| R2 (b) plano | `cs.py upgrade` sem `--apply` sai 0 e **não escreve nada**: hash da árvore inteira igual, sem `.git`. Cada SKILL.md antiga do manifesto aparece numa linha com `delete`/`remove`, e a nova correspondente aparece no plano | `test_plano_lista_a_troca_e_nao_escreve` |
| R2 (b) troca | `upgrade --apply --allow-outside` sai 0. Toda SKILL.md antiga do manifesto some, **e a pasta também** (exceto a pasta que tem arquivo humano, ver abaixo). A nova correspondente existe com o marcador de gerado | `test_apply_remove_as_pastas_antigas_do_manifesto_e_cria_as_novas` |
| R2 (b) G7/órfão | Depois do apply: `emit validate` sai 0. O manifesto não lista nome antigo. Nenhum arquivo do manifesto nem de `.swarm/bin`/`.swarm/harness` cita nome antigo. Nenhuma `<dir de skills>/<antigo>/SKILL.md` com marcador de gerado | `test_apply_emit_validate_verde_sem_orfao_e_sem_nome_antigo` |
| R2 (b) usuário | Pastas **do usuário** com nome antigo e **fora do manifesto** (`.cursor/skills/corrigir/`, `.agents/skills/salvar-sessao/`, `.github/skills/planejar-sprint/`) ficam byte a byte | `test_apply_preserva_pasta_do_usuario_fora_do_manifesto` (já passa hoje; M4 prova que o teste pega) |
| R2 (b) humano em pasta gerada | `.claude/skills/corrigir/minhas-notas.md` (humano, dentro de pasta gerada) fica, e a SKILL.md gerada antiga sai | `test_apply_preserva_arquivo_humano_dentro_de_pasta_gerada` |
| R2 versão | O `run.json5` do alvo passa a ter `skill_version` = VERSION da skill. Um segundo `cs.py upgrade` diz "nada a fazer" e não escreve | `test_apply_grava_versao_e_e_idempotente` (passa hoje por vácuo: 0.8.0 = 0.8.0; vira prova junto com o próximo) |
| R2 catálogo | VERSION ≥ 0.9.0. `migrations.json5` tem `version` = VERSION e uma entrada `to: "0.9.0"` com a ação `emit`, cujo texto cita pelo menos um nome novo | `test_catalogo_tem_entrada_090_e_version` |
| R3 bloco | `MODO-DE-USO.md` tem exatamente um par `<!-- skills:begin -->` … `<!-- skills:end -->`, com uma tabela no formato do §2.4 | `TestR3GuiaGeradoDoCodigo.test_guia_cobre_cada_skill_gerada_com_quem_roda_e_argumento` |
| R3 verdade independente | A tabela é confrontada com o que o **emit gera** no fixture (todas as plataformas, sem `*-playbooks`). Reprova: nome faltando, nome sobrando, "quem roda" incoerente com `disable-model-invocation`, argumento ≠ `argument-hint`, "para que serve" vazio | idem + `test_precondicao_verdade_tem_todas_as_familias` |
| R3 comando | `cs.py skills-guide --check` sai 0 na skill | `test_check_verde_na_skill` |
| R3 reprova divergência | Numa **cópia** da skill: tirar a linha de `/save-session`, acrescentar `/skill-fantasma-iter15` ou trocar "quem roda" de `/close-task` faz o `--check` sair ≠0 **nomeando** a skill. A cópia intacta passa | `TestR3CheckReprovaDivergencia.test_controle_…`, `test_reprova_skill_faltando`, `test_reprova_skill_sobrando`, `test_reprova_politica_de_quem_roda_trocada` |
| R3 regenera | `--write` restaura **exatamente** o guia gerado (o resto do arquivo fica intacto) e é idempotente | `test_write_regenera_e_preserva_o_resto` |
| R3 gerado do código | Mudar o `argument-hint` de `close-task` em `scripts/emit/platforms.py` da cópia deixa o guia velho (`--check` reprova, nomeando `close-task`). Depois do `--write`, a linha de `/close-task` traz o argumento novo | `test_tabela_vem_do_codigo` |
| R4 | Território com 73 invariantes (70 `rules.*` + 3 `rat.*`). O emit sai 0, `emit budget` e `emit validate` saem 0. No S2 de Claude Code, Cursor e Copilot, a seção Invariantes tem a linha `Mais N invariante(s): lista completa e priorizada em \`<arq>\`` com N = 73 − mostrados. `<arq>` existe, é gerado, está no manifesto e traz os 73. Os 3 `rat.*` (maior prioridade) estão entre os mostrados. No Codex, o `src/billing/AGENTS.md` aninhado também tem a linha | `TestR4InvariantesAlemDoOrcamento.*` (4) |
| R4 regressão | Com 3 invariantes (cabem), nenhuma linha "Mais N", todos listados | `TestR4PoucosInvariantesSemCorte.test_sem_linha_mais_quando_cabe` |

**Prova do R4 contra o HEAD** (pedida pelo founder). Numa cópia da skill viva com `scripts/emit/render.py` trocado pelo de
`git show HEAD:codebase-specialists/scripts/emit/render.py`, os 4 testes de `TestR4InvariantesAlemDoOrcamento`
**falham**, com `emit: S2 território de 'dev-billing': invariantes+regras+armadilhas somam 78 linhas > 58`. A regressão
de poucos invariantes passa. Com o `render.py` atual, os 5 passam. A saída está em
`…/scratchpad/iter15-mut/r4-head.txt` e `r4-live.txt`.

## 2. Interfaces FIXADAS

### 2.1 Mapa de nomes (R1)
`salvar-sessao→save-session`, `carregar-sessao→load-session`, `corrigir→correct`, `planejar-sprint→plan-sprint`,
`new-epico→new-epic`, `close-epico→close-epic`. Valem em todo diretório de skills emitido: `.claude/skills/`,
`.cursor/skills/`, `.github/skills/` e `.agents/skills/`. A regra é "o que a 0.8.x gerava em cada plataforma, a 0.9.0
gera com o nome novo". O oráculo **não** exige skill nova em plataforma onde a 0.8.x não gerava; por exemplo, hoje a
de sessão só sai no Claude Code. Ficam iguais: `feature-autonoma`, os subcomandos do motor (`cs-state new epico`,
`cs-mem correct`) e a prosa em português.

### 2.2 O que conta como "nome antigo" (regex `OLD_NAME_RE`)
- Os 5 nomes hifenizados contam em qualquer lugar, como token (`(?<![\w-])…(?![\w-])`).
- `corrigir` só conta como nome: `/corrigir` (comando ou caminho `…/corrigir/`, mas não `corrigir.md`),
  `` `corrigir` `` em crase, ou `name: corrigir`. A prosa "Se o usuário corrigir a saída…" continua permitida.

### 2.3 Exceções da varredura de fontes (R1)
- `references/migrations.json5`: a entrada 0.9.0 precisa citar os nomes antigos.
- `scripts/upgrade/**`: é onde mora o mapa antigo→novo, se a implementação precisar de um.
- `docs/PONTOS-DO-FOUNDER.md` e `docs/ROADMAP-rodada-seguinte.md`: registros históricos.
- Nos `.md`, linhas dentro de seção cujo título (ou ancestral) casa `migra|legad|0\.9`. O guia pode ter, por exemplo,
  "## Migrar para 0.9.0" explicando a troca.
- Não se varre: `tests/`, `fixtures/`, `evals/` e nomes de arquivo de template (renomear `state/new-epico.md` é escolha
  de quem implementa).

### 2.4 Seção do guia (R3)
- `MODO-DE-USO.md` tem **um** `<!-- skills:begin -->` e **um** `<!-- skills:end -->`, nessa ordem. Entre eles vai uma
  tabela Markdown. O cabeçalho tem colunas cujo texto contém `Skill`, `Para que serve`, `Quem roda` e `Argumento`;
  a comparação ignora maiúsculas e aceita colunas extras.
- Cada linha tem exatamente um `/<nome>` na coluna Skill.
- **Quem roda**: para a skill humana (`disable-model-invocation: true` no Claude Code ou, só no Codex, "só o humano
  executa" no corpo), a célula contém "só o humano". Para as demais, contém "modelo" e não contém "só o humano".
- **Argumento** = o `argument-hint` gerado (Claude Code, senão a 1ª plataforma que o tenha), ignorando crases e `\|`.
  Sem hint, a célula é `—`, `-`, vazia ou "nenhum".
- **Para que serve**: 10 caracteres ou mais.
- **Comando**: `python3 <skill>/scripts/cs.py skills-guide --check` sai 0 se o bloco é igual ao que o código gera.
  Se diverge, sai ≠0 e cita o nome da skill divergente na saída. `--write` regenera só o bloco, de forma idempotente,
  sem tocar o resto do arquivo. Não depende de alvo: roda com qualquer `--target`/cwd.
- A **fonte** é o código (`scripts/emit/platforms.py`). A forma de ler é livre: função, refatoração das skills de
  comando numa tabela etc. O `--check` precisa estar no checador de doctests (`test_commands_parse`), o que acontece
  sozinho se o subcomando existir no `cs.py`.

### 2.5 Migração 0.9.0 (R2)
- `cs.py upgrade --apply` num alvo 0.8.x remove **só** o que o manifesto do emit (`.swarm/emit/manifest.json5`) gerou e
  ainda tem o marcador `codebase-specialists:generated`.
- A pasta da skill sai quando fica vazia. Se tem arquivo humano, a pasta fica com ele.
- Pasta de mesmo nome **fora** do manifesto nunca é tocada.
- `migrations.json5`: entrada `{to: "0.9.0", why: "…", actions: [… {kind: "emit"} …]}`, com `version` = VERSION.

### 2.6 R4
`render.invariants_path(<agente>)` (`.swarm/knowledge/invariants/<agente>.json5`) é o arquivo apontado. O oráculo só
exige que o caminho citado na linha exista, seja gerado, esteja no manifesto e traga a lista completa.

## 3. Força: mutações (implementação de referência + 10 mutantes)

Para provar que o oráculo é passável e que pega defeito real, montei uma **implementação de referência descartável**
numa cópia (`<scratch>`, cópia da skill viva + rename + 0.9.0 + rmdir da pasta
vazia + `cs.py skills-guide` + bloco no guia). Com ela, o oráculo dá **28/28 OK**. A suíte da própria skill fica igual
à da viva (ver §5). Cada mutante parte da referência, muda uma coisa e roda o oráculo inteiro (`mutate.py`; saída em
`mutantes.txt`):

| Mutante | Resultado | Testes que reprovam (principais) |
|---|---|---|
| M1 renomeia só no Claude Code: Cursor/Copilot/Codex continuam `new-epico`/`close-epico`, mas coerente, com validate verde | 11 falhas | R1 init `test_cada_plataforma…`, `test_renomeadas…`, `test_nenhum_nome_antigo…`; R2 plano/troca/G7; R3 guia |
| M2 upgrade não remove a antiga (sem poda do manifesto) | 6 falhas | R2 plano, troca, G7/órfão, usuário/humano, versão |
| M3 upgrade apaga a SKILL.md mas deixa a pasta antiga vazia | 1 falha | `test_apply_remove_as_pastas_antigas…` |
| M4 upgrade apaga também a pasta do usuário fora do manifesto e a pasta com arquivo humano | 3 falhas | `test_apply_preserva_pasta_do_usuario…`, `test_apply_preserva_arquivo_humano…` (+ fontes) |
| M5 o gerador do guia esquece `feature-autonoma`, e o `--check` fica verde consigo mesmo | 1 falha | `test_guia_cobre_cada_skill…` (a verdade vem do emit, não do comando) |
| M6 o guia diz que o modelo roda tudo | 1 falha | `test_guia_cobre_cada_skill…` |
| M7 `render.py`/orchestrator continuam com `/salvar-sessao` e `/corrigir` | 4 falhas | `test_claude_md_e_orchestrator…`, `test_nenhum_nome_antigo…`, fontes, G7 pós-upgrade |
| M8 sem a migração (VERSION 0.8.0, sem entrada 0.9.0) | 5 falhas | `test_catalogo…`, R2 plano/troca/G7 |
| M9 `render.py` de HEAD (R4) | 4 falhas | os 4 de `TestR4InvariantesAlemDoOrcamento` |
| M10 corta os invariantes sem a linha "Mais N" | 2 falhas | `test_linha_mais_n…`, `test_codex_nested…` |

## 4. Base (skill viva, `base.txt`)
Python 3.13.3 e 3.9.6 dão o mesmo resultado: 28 testes, **19 falham**. Os 9 que passam:
- 5 do R4: o `render.py` não commitado já implementa o R4.
- `test_emit_validate_verde`: regressão.
- `test_precondicao_alvo_08…`: pré-condição.
- `test_apply_preserva_pasta_do_usuario…`: regressão; passa hoje porque o upgrade não faz nada. M4 prova que o teste pega.
- `test_apply_grava_versao…`: vácuo hoje (0.8.0 → 0.8.0).

Observação: a árvore viva já contém a iter14 sem commit e sem subir versão. Por isso, no alvo 0.8.x (HEAD),
`emit validate` acusa hoje `auto-approve/SKILL.md` desatualizado depois de um upgrade "nada a fazer". A 0.9.0 resolve
isso, porque o `emit` da migração reemite tudo.

## 5. Testes congelados que mudam (`mudanca-oficial/`)
Na skill (`--include=*.py`), **nenhum** teste exige os nomes antigos. As únicas ocorrências são prosa ("corrigir
arredondamento", "corrigir docs/…"), e o regex não as pega. Comparei a suíte da skill (`scripts/*/tests`, por pacote) entre a cópia viva e a referência: o resultado foi idêntico.
`doctests` 19 OK, `emit` 55 OK, `harness` 291 OK, `memory` 14 OK, `probes` 72, `scan` 90, `stage` 51, `team` 61 OK.
Os erros de carga em `facts`, `interview`, `panel` e `verify` são iguais nas duas e vêm do meu jeito de descobrir os
testes, não da mudança.
Há dois **oráculos anteriores** da campanha que congelam os nomes antigos e precisam do patch (detalhes em
`mudanca-oficial/PORQUE.md`):
- `iter10-test_estado_arvore.patch` (`TestSkillsEmitidas`: `SKILLS_CLI`, `CRIACAO`, `MUDANCA`, `DOR_FLAGS`)
- `iter13-test_menores.patch` (tupla `SKILLS`)

## 6. Decisões do autor do oráculo (para o founder conferir)
1. **Pasta vazia sai**: "remove as pastas" foi lido literalmente; não basta apagar a SKILL.md. Pasta com arquivo
   humano dentro **fica** (só a SKILL.md gerada sai). Quem não quiser essa regra tira
   `test_apply_preserva_arquivo_humano_dentro_de_pasta_gerada`.
2. **VERSION ≥ 0.9.0**, não `== 0.9.0`, para não brigar com a iter14 se ela subir versão antes. A entrada `to: "0.9.0"`
   é obrigatória.
3. **Plataformas**: o rename vale onde a 0.8.x já gerava a skill. O oráculo não obriga a passar a gerar `save-session`
   e as outras de sessão em Cursor/Copilot/Codex. O kernel dessas plataformas pode citar `/correct` ou deixar de citar.
   Só não pode citar `/corrigir`.
4. **Exceções da varredura** (§2.3): os registros históricos `docs/PONTOS-DO-FOUNDER.md` e
   `docs/ROADMAP-rodada-seguinte.md` ficam como estão. Seção de migração nos guias pode citar os nomes antigos.
5. **Interface do R3**: `cs.py skills-guide --check|--write`, com os marcadores `<!-- skills:begin|end -->` e as 4
   colunas. "Quem roda" usa o vocabulário "só o humano" / "modelo" (o mesmo da seção de hoje).
6. **Dependência textual única**: `test_tabela_vem_do_codigo` procura o literal `"<id da task> <resumo>"` (hint de
   `close-task`) em `platforms.py`. Se a implementação mudar esse hint, o teste falha na pré-condição e o repositório-piloto
   ajusta a constante `HINT_PROBE_OLD`.
7. A referência e os mutantes ficam fora do oráculo, em scratch. São evidência, não entrega.
