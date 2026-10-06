# Modo autônomo (0.8.0)

O modo autônomo deixa o time entregar uma feature (ou uma sprint) sem você a cada passo, com um **mandato** que
você assina. Regra de ouro: **o modelo só executa tasks; o script decide**. O piloto é `.swarm/bin/cs-auto`
(`motor: scripts/harness/engine/auto.py`); cada transição é um evento encadeado em `events.jsonl`
(`mandato.<transição>`).

## O mandato

Objetivo + critérios de aceite executáveis (`--criterio 'AC-n|texto|<teste ou comando>'`) + regressão (`--regressao`)
+ nós do plano + orçamento. Na proposta, o motor recusa: critério já verde (não prova entrega), classe trivial ou
`--nos` menor que 2 ("task avulsa"), spec ausente, mandato já aberto. O **orçamento é derivado do tamanho do plano**
(despachos, tentativas, replanos, minutos) e só o humano o altera, na aprovação (`cs-auto approve --orcamento`) ou
numa emenda (`cs-auto amend --orcamento`).

## Fluxo

1. `cs-auto propose` (`--feature FEA-nnn` ou `--sprint SPR-nnn`, `--spec`, `--objetivo`, `--nos`, `--criterio`,
   `--regressao`, `--classe`, `--portao`, `--rigor lean|standard|paranoid`) imprime `MAN-nnn`.
2. Humano: `cs-auto status` para ler, `/auto-approve` para assinar — no **terminal** dele, com a senha (ver
   "Senha e selo"). Aprovar assina o aceite, a regressão e o ponto seguro.
3. Plano: o modelo monta com `cs-auto plan add-node` / `edit-node` / `reset` e entrega com `cs-auto plan submit`.
   O motor valida: DAG sem ciclo, nós no território do agente, cobertura dos critérios, plano dentro do orçamento,
   ondas calculadas, lições consultadas.
4. Execução: `cs-auto tick` em laço (`/auto-tick`). Cada chamada retorna uma única ação; o modelo a executa e chama
   `tick` de novo. Verificar, aceitar e fechar task são trabalho do script, nunca do modelo. Cada task é verificada
   pelo próprio teste; o aceite da feature é medido só ao fechar cada onda.
5. Apoio a `tick`: `cs-auto reflect <task> --texto … --evidencia …` (reflexão de task), `cs-auto orphan <task>`
   (subagente morreu: sem mudança no disco a task volta à fila; com mudança vai direto à verificação),
   `cs-auto final-review --by … --verdict …` (revisão final), `cs-auto spend --usd …` (custo registrado),
   `cs-auto escalate --condicao …` (escalada com pacote de opções).
6. `/auto-report` (`cs-auto report`): critérios verdes, verificações com hash, itens devolvidos.

## Máquina de 12 estados

- **PROPOSED**: proposta feita, aguardando humano (`approve`, `amend`, `abort`).
- **CHARTERED**: aprovado e assinado; falta o plano.
- **PLANNING**: plano sendo montado/submetido (também a porta de entrada da próxima feature de um mandato de sprint).
- **RUNNING**: ondas em execução via `tick`.
- **INTEGRATING**: onda fechada; o motor avalia, nesta ordem, concluir, seguir para a próxima onda ou replanejar.
- **REPLANNING**: replano com evidência citada, nós aceitos intocados.
- **AWAITING_HUMAN**: nada mais pode rodar; pacote de escalada aberto.
- **PAUSED**: pausa (manual, ou pelo hook PreCompact); retomada volta ao estado de origem.
- **WRAPPING_UP**: encerrando com entrega parcial (gatilhos: orçamento aos 80%/100%, sem progresso, stop humano,
  critérios órfãos, encerrar).
- **DONE**: todos os critérios verdes e revisão final aprovada. Terminal.
- **HANDED_BACK**: entrega parcial, relatório gerado, pendências devolvidas ao backlog. Terminal.
- **ABORTED**: abortado pelo humano com motivo. Terminal.

## Portão humano

`approve`, `amend`, `resolve`, `stop` e `abort` exigem `--by <humano>` (o `approve`, também a senha no terminal) e o
guard bloqueia o modelo de rodá-los — e também `cs-auto senha …` e `cs-auto conferir`
(nas skills: `/auto-approve`, `/auto-amend`, `/auto-resolve`, `/auto-stop`, `/auto-abort`). As 4 skills do modelo são
`/auto-status`, `/auto-plan`, `/auto-tick`, `/auto-report`. `cs-auto resolve --choice` aceita `retomar`,
`trocar-agente` (com `--agent`), `emendar`, `descartar-ramo`, `encerrar`, `abortar`, sempre com `--decision`.

## Senha e selo

A aprovação exige a **senha do humano**, não só o `--by` e o guard (um agente que chamasse o motor por outro caminho
— pty, import, edição do estado — aprovaria sozinho).

- **1ª vez:** `cs-auto senha definir`, no terminal do humano. Senha forte (≥ 12 caracteres, ≥ 6 distintos, ≥ 3
  classes entre minúscula, maiúscula, dígito e símbolo), digitada duas vezes com o eco desligado. O registro fica
  **fora do repositório**: `~/.config/codebase-specialists/senha.json` (ou `$CS_SENHA_FILE`, que é só um caminho e é
  recusado se cair dentro do alvo), modo 0600, só com sais e o verificador PBKDF2-SHA256 (600000 iterações); a senha
  nunca é gravada. Trocar a senha pede a atual.
- **`cs-auto approve --by <humano> [--orcamento …]`** pede a senha no terminal. Ela só é lida de `/dev/tty`, com a
  stdin também em terminal: nenhum argumento, variável de ambiente ou stdin em pipe a fornece, e argumento extra no
  `approve` é recusado. Sem senha definida, sem terminal ou com a senha errada: exit ≠ 0, o mandato continua
  PROPOSED e nada é gravado. A senha não substitui o `--by` humano.
- **Selo:** o evento `mandato.approve` grava `data.selo` = `{versao, alg: hmac-sha256, mandato, plano_sha256,
  orcamento, seq, ts, tag}`, com `tag = HMAC-SHA256(K, …)` e `K` derivada da senha (PBKDF2 com outro sal). O
  `plano_sha256` cobre alvo, features, spec, objetivo, classe, rigor, portões, regressão, critérios, orçamento e os
  arquivos protegidos.
- **Antes de qualquer avanço** (`tick`, e o mesmo ponto central em `plan submit`, `resume` e nas transições do piloto)
  o motor lê o último `mandato.approve` do mandato na cadeia e recusa (ASK_HUMAN citando o selo, sem gravar evento)
  se: não há selo; o selo está fora do formato; é de outro mandato; o orçamento atual difere do aprovado (só o acréscimo
  de replano decidido pelo humano em `resolve --choice retomar` é somado); ou o hash do plano atual difere do selado.
- **`cs-auto conferir`** (humano, no terminal, com a senha) recalcula a HMAC de **todos** os selos da cadeia e nomeia
  cada aprovação ruim (`MAN-nnn seq N`). Não muda o estado.

**Limite honesto:** o `tick` roda sem a senha, então **não verifica a HMAC**: uma tag forjada no formato certo, sobre
os campos certos, passa por ele. O que o tick garante é que aprovação sem selo, selo malformado, de outro mandato, ou
plano/orçamento alterados depois (mesmo reescritos de forma consistente na cadeia) não avançam. Quem verifica a HMAC
é só o `cs-auto conferir` digitado pelo humano. E o registro da senha é legível/gravável pelo agente: ele pode apagá-lo,
definir a senha dele e re-selar — o humano descobre ao conferir, porque a senha REAL passa a ser recusada.

## Orçamento e corte

Aos **80%** o corte é suave: com 5 despachos, o 4º ainda sai e termina, o 5º nunca sai; o mandato entra em
WRAPPING_UP e entrega parcial, devolvendo o restante ao backlog. Sem progresso (rodadas que não avançam o aceite) o
motor replaneja **uma vez**; se continuar parado, encerra com entrega parcial em vez de escalar por contagem.

## Ramo travado

Task que precisa de área congelada (ou foi escalada) trava só o seu ramo e quem depende dele. O mandato vai a
AWAITING_HUMAN apenas quando não sobra nenhum nó executável. As opções do `resolve` estão no pacote da escalada.

## Pausa e retomada

`cs-auto pause [--motivo …]` marca o que está em voo; `cs-auto resume` volta exatamente ao estado anterior
(confere o carimbo). O PreCompact pausa um mandato em andamento sozinho (sem mandato, não faz nada). O tempo pausado
não consome o orçamento de minutos.

## Fora de escopo nesta versão

Promoção de lições no fim, diário, modelo do verificador maior ou igual ao do autor, revisão cega, custo medido
pelo roteador e modo semiautônomo para plataformas sem hook.

Migração: veja [09-upgrade.md](09-upgrade.md) (Migração 0.8.0).
