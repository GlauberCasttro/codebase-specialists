# ESPEC — oráculo da campanha iter20 (B-13, patch 0.10.1)

Oráculo `test_iter20.py` (unittest puro, Python 3.9+, repositórios git temporários, CLI real em subprocesso — `cs.py`
e o hook git de verdade, sem mock). Skill sob teste: `$CS_SKILL_DIR` (padrão: a raiz deste projeto). Rodar (desta
pasta): `python3 -m unittest -v test_iter20`; placar por requisito: `python3 medir.py`. Cerca de 1 min por Python.

Base medida em `base.txt`: a cópia de trabalho da iter18 (0.10.0, ainda sem commit; é o que vira HEAD), com python3
3.13 e /usr/bin/python3 3.9.6. Os resultados são iguais nos dois: **16 D falham e 8 R passam**.

Legenda: **D** = defeito (falha na base e passa depois da correção). **R** = não-regressão ou sem brecha (passa
antes e depois). O `medir.py` classifica como R os testes cujo nome contém `regressao|controle|continua|intacta`.

## Problema (achado de uso real na cobaia .NET)
O pre-commit do alvo (`.git/hooks/pre-commit` → `.swarm/bin/cs-precommit` → `validate.py` e depois
`guard.py check-diff --staged`) barra o resultado da própria ferramenta. O `upgrade --apply`, o `emit` avulso e o
`harness install` avulso regravam o motor em `.swarm/harness/*`, que é área protegida, e os artefatos emitidos
(`.claude/agents/*`, `.claude/orchestrator.md`, `.claude/skills/*/SKILL.md`, CLAUDE.md…), que ficam fora de qualquer
allowed_paths. Na base, o upgrade só commita com `--no-verify`, e o founder não autoriza isso: a correção tem de
estar na causa raiz.

## Fixture (reprodução da cobaia)
- **Skill antiga REAL:** `git archive 5617806` deste repositório, que é o commit da 0.9.0. É extraída num diretório
  temporário e nada é escrito no repositório. Para apontar outra cópia, use `$CS_OLD_SKILL_DIR`.
- **Alvo 0.9.0:** repositório sintético da fixture do emit (time aprovado: dev-billing, dev-web, reviewer, qa), com
  `git init` e commit. Com a skill 0.9.0 rodam `cs.py init --platforms claude-code`, `harness install
  --allow-outside` e `emit --allow-outside`, e tudo é commitado. Depois roda `harness install --git-hook`, que liga
  `.git/hooks/pre-commit` → `../../.swarm/bin/cs-precommit` como o install faz. O hook só é ligado depois do commit
  da geração, então **a fixture nunca usa `--no-verify`**.
- **Sonda contra teste vazio:** a fixture confere que o hook barra uma fonte fora de allowed_paths. Todo commit do
  teste usa `-c core.hooksPath=<alvo>/.git/hooks`, para que uma configuração global da máquina não desligue o hook.
  Todo "commit passa" exige exit 0, HEAD andando e a saída `validate` do hook.
- **O que entra no commit:** `git add -A`, ou seja, tudo o que o `git status` mostra, respeitado o `.gitignore` do
  alvo. Isso inclui `.swarm/backups/upgrade-*` enquanto ele não for ignorado. Ignorar os backups ou não fica a
  critério do corretor; o teste só exige que o commit passe.
- Arquivos usados: `ENGINE_FILE=.swarm/harness/guard.py` e `.swarm/harness/views.py`, que o upgrade 0.9.0→0.10.x
  regrava porque mudaram na iter18; `EMIT_CHANGED=.claude/orchestrator.md`, que o upgrade muda;
  `EMIT_SAME=.claude/skills/board/SKILL.md`, que o emit regrava com o mesmo conteúdo; `SRC_OUT=src/web/app.py`;
  `USER_SKILL=.claude/skills/minha-skill/SKILL.md`; `ENGINE_NEW=.swarm/harness/extra.py`.

| req | D (base) | R (base) | total base |
|---|---|---|---|
| U1 o resultado da ferramenta commita sem --no-verify | 0/5 | — | 0/5 |
| U2 edição/remoção manual na mesma leva é barrada | 0/1 | 4/4 | 4/5 |
| U3 fora do conjunto escrito e fora de allowed_paths é barrado | — | 3/3 | 3/3 |
| U4 o atestado não é reutilizável | 0/4 | 1/1 | 1/5 |
| U5 versão 0.10.1 e 0.9.0 → 0.10.1 direto | 0/6 | — | 0/6 |
| total | 0/16 | 8/8 | 8/24 |

## U1 — o resultado do upgrade, do emit e do install commita sem --no-verify (D)
| Requisito | Teste | Tipo |
|---|---|---|
| `upgrade --apply` (0.9.0 → atual) + `git add -A` + `git commit` passa; o upgrade regravou o motor e o orchestrator | `TestU1CommitDoResultadoDaFerramenta.test_u1_upgrade_commita_sem_no_verify` | D |
| `cs.py emit --allow-outside` avulso (re-emissão no alvo 0.9.0) → commit passa | `test_u1_emit_avulso_commita` | D |
| `cs.py harness install --allow-outside --git-hook` avulso → commit passa | `test_u1_harness_install_avulso_commita` | D |
| upgrade + task criada pelo `cs-state` (estado legítimo) na mesma leva → commit passa | `test_u1_upgrade_com_estado_do_cs_state_na_mesma_leva` | D |
| alvo novo só com a skill sob teste (`init` + `harness install --git-hook` + `emit`) → commit da instalação passa | `TestU1InstalacaoInicial.test_u1_instalacao_inicial_commita` | D |

**Critério:** a instalação inicial entra porque o B-13 cita "emit/harness install avulsos" e o mecanismo é o mesmo.
Na base, ela também só commita com `--no-verify`.

## U2 — edição manual na mesma leva continua barrada
| Requisito | Teste | Tipo |
|---|---|---|
| motor regravado pelo upgrade e editado à mão antes do commit → barrado (`FORA: .swarm/harness/guard.py`) | `TestU2EdicaoManualNaMesmaLeva.test_u2_motor_editado_a_mao_continua_barrado` | R |
| emitido que o upgrade mudou (orchestrator), editado à mão → barrado | `test_u2_emitido_mudado_pelo_upgrade_editado_a_mao_continua_barrado` | R |
| SKILL.md emitida (regravada sem mudança), editada à mão → barrada | `test_u2_skill_emitida_editada_a_mao_continua_barrada` | R |
| arquivo do motor REMOVIDO à mão depois do upgrade → barrado (a recusa cita o arquivo) | `test_u2_motor_removido_a_mao_barra` | **D** |
| task gravada pelo `cs-state` e editada à mão → barrada (hoje é o `validate` do hook: "edição à mão em .swarm/state/tasks/…") | `test_u2_estado_editado_fora_do_cs_state_continua_barrado` | R |

**Achado da medição (remoção, D):** o `check_diff` lista os arquivos com `git diff --name-only --cached`, que detecta
renomeação. O backup do upgrade guarda uma cópia idêntica do motor em `.swarm/backups/upgrade-*/specialists/harness/`.
Por isso, remover `.swarm/harness/views.py` à mão e fazer `git add -A` aparece como **renomeação** para dentro do
backup. Só o nome novo (`.swarm/`, que é liberado) é conferido e a remoção passa calada. Na base, a remoção só é
"barrada" junto com o resto do upgrade, e a recusa não cita o arquivo. O teste exige que a recusa cite o arquivo
removido. O corretor escolhe a solução: `--no-renames`/`--name-status`, o conjunto de remoções da ferramenta, ou ignorar
os backups. Remoções feitas pela PRÓPRIA ferramenta, como a poda do emit na 0.9.0, devem passar como qualquer escrita
dela. O caminho 0.9.0→0.10.x não tem poda, então isso não é testado aqui.

**Critério (estado):** hoje quem barra a edição de estado é o `validate.py` do hook ("o arquivo difere do que o motor
gravou"), antes do `check-diff`. A correção não pode tratar arquivo de estado como "escrito pelo upgrade" e com isso
pular a validação.

## U3 — fora do que a ferramenta escreveu e fora de allowed_paths: barrado (R)
| Requisito | Teste | Tipo |
|---|---|---|
| fonte (`src/web/app.py`) staged sozinha depois do upgrade → `FORA: src/web/app.py` | `TestU3ForaDoConjuntoEscrito.test_u3_fonte_fora_de_allowed_continua_barrada` | R |
| skill do usuário nova (`.claude/skills/minha-skill/SKILL.md`) → barrada | `test_u3_skill_do_usuario_continua_barrada` | R |
| arquivo novo no motor (`.swarm/harness/extra.py`) → barrado | `test_u3_arquivo_novo_no_motor_continua_barrado` | R |

**Não-regressão rodada JUNTO pelo portão:** os oráculos congelados `campanhas/iter18/oraculo:test_iter18` (R5:
allowed_paths de task aberta com delegação DISPATCHED/RETURNED/VERIFIED/REVIEWED barrados no `--staged`; ACCEPTED com
a task aberta libera; `.swarm/**` liberado; task fechada barra) e `campanhas/iter16/oraculo:test_uso_real` (U5:
`TestU5CheckDiffDepoisDoAceite` e `TestU5OrchestratorInstruiCommitAntesDoClose`). Conferido nesta base:
`test_iter18.TestR5PreCommitSoDepoisDoAceite` 7/7 OK; os dois `TestU5*` do iter16, 7/7 OK. Portão sugerido:
`portao.sh iter20 --oraculo campanhas/iter20/oraculo:test_iter20 --oraculo campanhas/iter18/oraculo:test_iter18
--oraculo campanhas/iter16/oraculo:test_uso_real -- <arquivos>`. Os D do iter18 que dependem de versão (R8: 0.10.0)
deixam de valer com a 0.10.1, porque são testes de versão. O critério da iter20 é R5 inteiro verde, mais R1–R7.

## U4 — o atestado não é reutilizável
| Requisito | Teste | Tipo |
|---|---|---|
| upgrade commitado (passa) → 2º commit com o motor editado à mão → barrado | `TestU4AtestadoNaoReutilizavel.test_u4_segundo_commit_motor_a_mao_barra` | D |
| upgrade commitado → 2º commit com orchestrator e SKILL.md editados à mão → ambos barrados | `test_u4_segundo_commit_emitido_a_mao_barra` | D |
| upgrade commitado → motor editado → `upgrade --apply` de novo ("nada a fazer") → commit continua barrado | `test_u4_reupgrade_sem_migracao_nao_abencoa_edicao` | D |
| upgrade + intrusos (fonte, skill do usuário, arquivo novo no motor) → barra e cita SÓ os intrusos, nenhum arquivo que o upgrade escreveu; depois do `git reset` dos intrusos, o commit passa | `test_u4_atestado_nao_libera_intruso` | D |
| `emit` avulso (não mexe no motor) + motor editado à mão → barrado | `test_u4_emit_avulso_nao_libera_motor_editado_continua` | R |

Os D do U4 são D porque cada um começa pelo commit do upgrade, que precisa passar. Na base, falham aí.
O bloqueio do 2º commit é a parte que impede atalhos do tipo "libera `.swarm/harness/**` e `.claude/**`".

**Risco não coberto por comportamento (fica para a revisão):** o atestado/manifesto em si. Se ele morar numa área que
o lead escreve (`.swarm/`) e o check-diff confiar no conteúdo dele sem conferência, quem edita o manifesto abençoa
qualquer arquivo. O oráculo não testa o formato, então o revisor confere que o atestado não pode ser forjado com uma
edição simples. Opções: o hash do conteúdo staged confere com o que a ferramenta escreveu, o atestado é consumido no
commit, ou ele fica fora da árvore versionada.

## U5 — versão 0.10.1 (D)
| Requisito | Teste | Tipo |
|---|---|---|
| `VERSION` = 0.10.1 | `TestU5Versao.test_u5_version` | D |
| `migrations.json5`: `version: "0.10.1"`; uma entrada `to: "0.10.1"`, logo depois da 0.10.0 e a última; actions ⊇ {harness} | `test_u5_migrations` | D |
| README cita 0.10.1 | `test_u5_readme` | D |
| `docs/09-upgrade.md` tem o título `## Migração 0.10.1…` | `test_u5_docs_upgrade` | D |
| alvo 0.9.0: o plano (`cs.py upgrade`, sem escrever nada) mostra a skill 0.10.1, "migrações no intervalo (2)", as linhas 0.10.0 e 0.10.1 | `TestU5DeZeroNoveDireto.test_u5_plano_de_090_lista_0100_e_0101` | D |
| alvo 0.9.0: `upgrade --apply` deixa `skill_version` 0.10.1 e `upgrade_history[-1]` com `from` 0.9.0 e `migrations` [0.10.0, 0.10.1] | `test_u5_apply_de_090_registra_as_duas_migracoes` | D |

**Critério (migração):** o pre-commit e o motor mudam, então o alvo precisa reinstalar o harness. Por isso
`{kind: "harness"}` é obrigatório. `{kind: "emit"}` fica a critério do corretor e só é necessário se algum emitido
mudar ou se o mecanismo exigir que o emit registre o que escreveu. Num alvo que já está em 0.10.0, o emit não roda
sem essa entrada. O U1 cobre o caminho 0.9.0 → 0.10.1, com as duas migrações e as duas ações.

## Fora do escopo do oráculo
- O formato do manifesto/atestado e onde ele mora (comportamento apenas).
- Cursor/Copilot/Codex: o alvo do teste é claude-code. O pre-commit é o mesmo `cs-precommit`.
- Upgrade 0.10.0 → 0.10.1 isolado: não existe commit da 0.10.0 para extrair enquanto a iter18 não for commitada. O
  caminho 0.9.0 → 0.10.1 aplica a mesma migração.
