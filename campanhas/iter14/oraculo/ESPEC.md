# ESPEC — oráculo campanha-iter14: a senha do humano na aprovação do mandato autônomo

**Defeito:** no modo autônomo (máquina `mandato`, `scripts/harness/engine/auto.py`, wrapper `.swarm/bin/cs-auto`,
skill humana `/auto-approve`, doc `docs/11-modo-autonomo.md`), `cs-auto approve --by … --orcamento …` **não pede a
senha**. Só o guard (hook pre-bash) impede um agente de rodá-lo; um agente que chame o motor por outro caminho
(pty, import, edição do estado) aprova sozinho. A doc e o SKILL.md prometem "`/auto-approve` (com a senha)".
**Decisão do founder:** ligar a senha de verdade.

**Padrão espelhado:** skill `auto-correcao` (`scripts/frase.py`: PBKDF2-SHA256 600000 + sal, força, leitura só por
`/dev/tty` com eco desligado e só se stdin for tty, selo HMAC por aprovação; `tests/_pty_helper.py`: humano simulado
por `pty.fork`). A skill `codebase-specialists` é pública: **não pode depender da auto-correcao instalada**.

Oráculo: `test_senha_mandato.py` (33 testes, unittest puro, Python 3.9+, POSIX/pty, alvos git temporários).
Base: `base.txt`. Mudança nos oráculos congelados: `mudanca-oficial/` (patch + `PORQUE.md`).
Quem implementa **não edita** o oráculo.

## 0. Como o oráculo observa (sem mock, sem bypass)
- `cs-auto` = `python3 <skill>/scripts/harness/engine/auto.py --root <alvo> …` em subprocesso.
  Skill: `$CS_SKILL_DIR`, senão `~/.claude/skills/codebase-specialists`.
- Fixtures do alvo (git + árvore iter10 + `propose`) reaproveitadas do oráculo do M5
  (`$CS_M5_ORACULO`, senão `../../campanha-m5/oraculo/test_mandato.py`), importado como módulo; as classes de teste
  dele não rodam aqui.
- **Humano** = pseudo-terminal real (`pty.fork`): o teste digita a resposta a cada prompt que casa
  `SENHA[^\r\n:]*:`. **Sem terminal** = stdin `/dev/null` (ou pipe com a senha) + `start_new_session=True`.
- A senha de teste (`Mandato-Seguro-2026`) só vale porque o teste grava, num `CS_SENHA_FILE` temporário, um registro
  no formato §2.1. `HOME` também é temporário em todo subprocesso: `~/.config` real nunca é lido nem escrito.
  Nenhuma variável de "senha" fica no ambiente (o teste remove `CS_SENHA`, `SENHA`, `CS_HUMAN_PROOF_ARGS` etc.).
- **Forjador** = agente com escrita no estado e sem a senha: reescreve `events.jsonl` re-encadeando `seq`/`prev` e
  troca o hash final onde estiver gravado (projeção), e/ou edita a projeção do motor (`.swarm/.engine/projection.json5`,
  achada pelo conteúdo: `last_event_hash` + `mandatos`). É o máximo que se faz sem a senha.

## 1. Requisitos → testes
| Req | Teste(s) | Negativos |
|---|---|---|
| S1 `senha definir` | `TestS1SenhaDefinir.*` (8) | sem terminal (stdin /dev/null e pipe); 5 senhas fracas; confirmação diferente; troca sem a senha atual; caminho dentro do alvo; registro da auto-correcao não serve |
| S2 `approve` com senha | `TestS2Approve.*` (8) | senha errada; sem terminal; stdin em pipe com tty controlador; `--senha X`, `--senha=X`, `--password X`, posicional; 6 variáveis de ambiente + `CS_HUMAN_PROOF_ARGS`; sem senha definida; registro com `iter` 1000 / `kdf` md5; `--by` não humano com a senha certa |
| S3 selo HMAC | `TestS3Selo.*` (2) | tag não confere com chave de senha errada |
| S4 `tick` recusa | `TestS4Tick.*` (6) | aprovação sem selo; selo com tag não-hex, curta, ausente, de outro mandato, sem `plano_sha256`, `alg` desconhecido, selo não-objeto; orçamento/objetivo/critério/regressão alterados depois; forja consistente na cadeia (orçamento reescrito no evento E na projeção); orçamento inflado em RUNNING |
| S5 `conferir` | `TestS5Conferir.*` (6) | senha errada; sem terminal; tag aleatória no formato; tag de outra senha; aprovação sem selo; registro de senha trocado pelo agente |
| S6 guard/skill/doc | `TestS6GuardEDoc.*` (3) | `senha definir`, `conferir`, `approve` (wrapper, `python3 auto.py`, `cd x && …`) bloqueados para principal e subagente; leitura (`grep 'senha definir' docs/…`) livre |
| S7 regressão | `mudanca-oficial/` (patch em `test_mandato.py` do M5 e em `test_cobertura_maquinas.py`) | — |

Guardas de regressão que **passam na base** (de propósito): `test_by_humano_continua_exigido_com_a_senha_certa`,
`test_tick_legitimo_avanca_ate_running_e_segue`. Os testes negativos de S1/S5 têm **controle positivo** no mesmo
teste (o comando precisa existir e funcionar), para não passarem no vácuo contra um produto sem o comando.

## 2. Interface FIXADA

### 2.1 Registro da senha (S1)
- Caminho: `$CS_SENHA_FILE` (só caminho, nunca conteúdo; existe para teste e para quem quiser outro lugar), senão
  `~/.config/codebase-specialists/senha.json` (`~` = `$HOME`). O oráculo remove `XDG_CONFIG_HOME`; honrá-lo é livre.
- **Fora do repositório-alvo:** se o caminho resolvido (realpath) cair dentro de `--root`, `senha definir` recusa
  (exit≠0) e não grava nada.
- Conteúdo JSON (igual ao v1 do `frase.py`, em arquivo e variável PRÓPRIOS):
  `{"versao": 1, "kdf": "pbkdf2-sha256", "iter": <int ≥ 600000>, "salt_verificador": <hex ≥16 bytes>,
  "salt_chave": <hex ≥16 bytes, ≠ salt_verificador>, "verificador": <hex 32 bytes>, "criada_em": <texto, opcional>}`.
  `verificador = PBKDF2-HMAC-SHA256(NFC(strip(senha)), salt_verificador, iter, 32)`. A senha nunca é gravada (nem a
  errada). Modo `0600`; diretório criado com `0700`.
- Registro inválido (kdf ≠ pbkdf2-sha256, `iter` < 600000, sais inválidos/iguais) ⇒ approve/conferir recusam.

### 2.2 Leitura da senha (S1, S2, S5)
- Só se `sys.stdin.isatty()` **e** `/dev/tty` abrir; eco desligado; prompt escrito no `/dev/tty`, contendo `SENHA` e
  terminando em `:` (regex `SENHA[^\r\n:]*:`). Uma leitura por prompt, sem laço de novas tentativas.
- **Sem fallback**: nenhum argumento (`approve` passa a recusar argumentos desconhecidos — o `parse_known_args` com
  `extras` para atos humanos deixa de valer), nenhuma variável de ambiente, nenhuma stdin em pipe.
- `cs-auto senha definir` (subcomando `senha`, ação `definir`): se já existe registro, pede primeiro a senha ATUAL
  (errada ⇒ exit≠0, registro intocado); depois a nova e a repetição (diferentes ⇒ exit≠0, nada gravado).
  Força (após NFC+strip): ≥ 12 caracteres, ≥ 6 distintos, ≥ 3 classes entre minúscula, maiúscula, dígito e símbolo.
- `cs-auto approve`: sem registro ⇒ exit≠0 com mensagem contendo `senha definir`; sem terminal, senha errada ou
  registro inválido ⇒ exit≠0, mandato continua `PROPOSED`, **nenhum** evento `mandato.approve`. A senha não substitui
  o `--by` humano: `--by orchestrator` com a senha certa continua exit 1 `guarda by_human`.

### 2.3 Selo (S3)
No evento `mandato.approve`, `data.selo` (objeto):
`{"versao": 1, "alg": "hmac-sha256", "mandato": "<MAN-nnn>", "plano_sha256": <hex64>, "orcamento": <orçamento
aprovado>, "seq": <int>, "ts": <texto ISO>, "tag": <hex64>}`
- `orcamento` = o orçamento aprovado, no mesmo formato que o mandato guarda (`{"despachos": 17, …}`; o oráculo também
  aceita `{"despachos": {"limite": 17}}`).
- `seq` = ordinal da aprovação **deste mandato** (1 na primeira; 2 depois de emenda + nova aprovação).
- `plano_sha256` = sha256 do contrato aprovado, **recomputável pelo motor a partir do mandato atual**; a escolha dos
  campos é do construtor, mas tem de cobrir pelo menos `objetivo`, `criterios`, `regressao` e `orcamento` (testado).
- `tag = HMAC-SHA256(K, canonical)`, `K = PBKDF2-HMAC-SHA256(NFC(strip(senha)), salt_chave, iter, 32)`,
  `canonical = json.dumps({mandato, plano_sha256, orcamento, seq, ts}, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False).encode("utf-8")`. O oráculo recalcula a tag com a senha de teste.

### 2.4 `cs-auto tick` (S4)
Antes de qualquer avanço com o mandato fora de `PROPOSED` e de terminal, o motor lê o ÚLTIMO `mandato.approve` desse
mandato **na cadeia** (`events.jsonl`) e recusa se: não há selo; selo fora do formato §2.3 (`versao`, `alg`, `tag` e
`plano_sha256` hex64, `seq` int, `ts` texto); `selo.mandato` ≠ id; `selo.orcamento` ≠ orçamento atual; ou
`selo.plano_sha256` ≠ hash recomputado do contrato atual.
Recusa observável (qualquer uma): **exit≠0** com `selo` no stdout/stderr, **ou** exit 0 com JSON `acao: ASK_HUMAN`
citando `selo`. Nos dois casos: mesmo estado e **nenhum** evento `mandato.*` novo; o 2º tick recusa de novo.
Selo legítimo não pode travar o piloto (PLAN → plano → DISPATCH → próximo tick, com uso de orçamento mudando).

**Limite honesto:** o tick roda sem a senha, então **não verifica a HMAC**. Uma tag forjada no formato certo, sobre os
campos certos, passa pelo tick. Quem verifica a HMAC é só o `cs-auto conferir` digitado pelo humano. O que o tick
garante: aprovação sem selo, selo malformado, selo de outro mandato e plano/orçamento alterados depois da aprovação
(inclusive reescritos de forma consistente na cadeia) não avançam.

### 2.5 `cs-auto conferir` (S5)
Humano, terminal + senha (§2.2). Recalcula a tag de **todo** `mandato.approve` da cadeia. Tudo válido ⇒ exit 0,
saída cita o mandato. Algum inválido (sem selo, tag que não confere) ⇒ exit≠0 nomeando cada evento ruim com o id do
mandato e `seq <N>` (seq da linha na cadeia; regex `seq\D{0,3}<N>\b`). Senha errada ou sem terminal ⇒ exit≠0.
Não muda o estado do mandato.
**Limite honesto:** o registro de senha é legível/gravável pelo agente. Ele pode apagá-lo, definir a senha dele e
re-selar. O humano descobre ao conferir: a senha REAL passa a ser recusada (testado).

### 2.6 Guard, skill humana, doc (S6)
- O guard (pre-bash, principal e subagente) bloqueia (exit 2) `cs-auto senha …`, `cs-auto conferir` e
  `cs-auto approve` (wrapper `.swarm/bin/cs-auto`, `python3 …/auto.py`, depois de `cd x &&`). `cs-auto tick`,
  `status` e comandos que só citam o texto (`grep 'senha definir' …`) continuam livres.
- `assets/templates/state/auto-approve.md`: cita `senha definir` (primeira vez), `cs-auto approve`, que a senha é
  digitada no **terminal** do humano; não cita `--senha`, `CS_HUMAN_PROOF_ARGS` nem `CS_SENHA=`.
- `docs/11-modo-autonomo.md`: trata de `senha definir`, `conferir`, `selo`, `HMAC`, `terminal` e declara o limite (o
  tick não verifica a HMAC sem a senha); não cita `--senha`.

### 2.7 Regressão (S7)
O approve sem terminal passa a falhar; os oráculos congelados que aprovam (`campanha-m5/oraculo/test_mandato.py` e o
oficial `scripts/harness/tests/test_cobertura_maquinas.py`, via `m5_cenarios.py`) precisam digitar a senha num pty.
Patch e justificativa em `mudanca-oficial/`. Sem o patch eles ficam vermelhos contra um produto correto.

## 3. Decisões para o founder conferir
1. **Força:** exige ≥ 3 classes (o `frase.py` também aceita frase de ≥ 3 palavras sem classes). O oráculo só testa
   senhas fracas de 1–2 classes e a senha forte de 4 classes: aceitar ou não uma frase de 3 palavras minúsculas fica
   livre para o construtor.
2. **Escopo da senha:** só `approve` (e `senha definir`/`conferir`). `amend`, `resolve`, `stop`, `abort` continuam
   com `--by` + guard. `resolve --choice retomar|trocar-agente` reabre execução sem senha; se o founder quiser,
   é uma rodada seguinte.
3. **Forma da recusa do tick:** aceita exit≠0 **ou** `ASK_HUMAN`; o que é fixo é "não avança, cita o selo".
4. **"Qualquer avanço autônomo":** o oráculo cobre o `tick` (CHARTERED e RUNNING). `plan submit`/`resume` direto
   depois de uma forja não são testados; recomenda-se o construtor checar o selo no mesmo ponto central.
5. **`seq` do selo** = ordinal da aprovação do mandato (não o seq da cadeia, que o motor só conhece ao anexar).
   O oráculo só observa `seq = 1` (re-aprovação exige escalada; não montada aqui).
6. **Registro separado da auto-correcao:** mesmo formato v1, arquivo/variável próprios; o `frase.json` da
   auto-correcao (mesma senha) **não** serve — testado numa cópia isolada da skill, sem a auto-correcao ao lado.
7. **`CS_HUMAN_PROOF_ARGS`** (gancho do M5 para a "prova humana") fica morto: senha por argumento é proibida. Os
   oráculos do M5 deixam de depender dele pelo patch (pty).
8. **Patch também no oráculo oficial** `test_cobertura_maquinas.py` (não só no `test_mandato.py` do M5): os cenários
   `m5_*` aprovam pela CLI real e quebrariam.

## 4. Prova de que o oráculo não é fraco
Ver `base.txt` (§ mutações): uma implementação de referência (só na cópia em scratchpad, nunca na skill) passa 33/33;
cada mutação (aceitar qualquer senha, não gravar selo, tick sem conferir, tick só formato, conferir aceitando tudo,
senha por ambiente, tag sem a chave da senha, guard sem `senha`/`conferir`, stdin em pipe aceita) reprova.

Rodar: `python3 -m unittest -v test_senha_mandato` (de dentro desta pasta; ~50 s).
