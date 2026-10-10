# PORQUÊ — mudança oficial 1 do oráculo iter21 (congelado em 680e14a019af)

Classe: **defeito do ORÁCULO** nas partes (1) a (3), mais um **requisito novo de uso real** (M13). O produto não muda.

- Patch: `campanhas/iter21/oraculo/mudanca-oficial/oraculo-iter21-mo1.patch` (5 arquivos). Aplicar da raiz do projeto:
  `patch -p0 < campanhas/iter21/oraculo/mudanca-oficial/oraculo-iter21-mo1.patch` (conferido com `--dry-run`).
- sha256 antes → depois:
  - `prova_real.py`  3db8de29c74991210c9b70f2d33490364f83c7c79aa04b1b301942eed8bd07f5 → 74d12c904352de7367b8fa11ef2d07c58219ab8efac47097440b45b2fba16f49
  - `test_iter21.py` 46baddee5d08325fd7383b722e12cd90dff8f25717eecad0d799233fdb5053c1 → 805a9a9474d77c4b55ad4027d68bca7879d7d71c3943240d4e7aa34dfd95883b
  - `medir.py`       f4b8e22a099b6d730cca0170334f61ac3a8ea6b38f5315d528f638cd7a6cfe16 → 227bd43abd6a0c5ba0e75ad6b21cdad939e1a26d5b7f9238b98f77887dd6dde5
  - `ESPEC.md`       97f9edd92d00c8b52180da6c136dac8b6cdc70cadda343b30302abf86461689f → b6c258714973770057418ad796be43e364a4c2bf9244700da248e2884fcfe0ec
  - `base.txt`       aeb0836b9818861e016a1362c2ce2f906152a35ebc30388f18430643dd96ffa3 → 127f2a68c319d3facaec826de1ffb2f2014e86571830eba50915a1154845c695
- Nenhum `def` foi removido. As 5 linhas `-def` do patch são mudanças de assinatura com parâmetros novos OPCIONAIS
  (`build_template`, `claude_argv`, `domain_facts`, `make_domain_repo`, `build_target`). Todo chamador antigo
  continua válido.

## Evidência (medição base real, `~/cs-prova-iter21/base/base/00/`, 1º despacho, US$ 0,347)
1. **Traceback do oráculo.** A linha 31 do `saida.jsonl` é
   `{"type":"system","subtype":"permission_denied","message":"Permission to use Bash has been denied. ..."}`, em que
   `message` é uma string. `tool_events()` fazia `(m.get("message") or {}).get("content")` e quebrava com
   `AttributeError: 'str' object has no attribute 'get'`, derrubando a rodada inteira.
2. **Origem do `permission_denied` (CONFIRMADO pelo stream, linhas 18–48, e pelo `obs.jsonl`).** O Bash NÃO foi negado
   ao agente como um todo. O subagente rodou `find … | sort`, `.swarm/bin/cs-mem check --agent dev-cultivo`,
   `python3 -m unittest tests.test_ok` e `.swarm/bin/cs-state submit …`, que devolveu `RETURNED`. O `result.permission_denials` tem
   duas negações de origens diferentes:
   - `python3 -m unittest tests.test_ok; echo "EXIT:$?"`, negado pelo **sistema de permissões do Claude Code**: é o
     único evento `system/permission_denied`. Comando composto: cada parte precisa casar com a allow-list da PROVA, e
     `echo` não estava nela (`--permission-prompts none` nega o que pediria confirmação). É um defeito do oráculo, e a
     correção é a allow-list mínima.
   - `.swarm/bin/cs-state verify --task …`, negado pelo **hook do produto**:
     `PreToolUse:Bash hook error: … cs-guard BLOQUEOU: subagente não roda cs-state verify`. É o comportamento correto
     do produto (verify é do orquestrador): é DADO de produto, e não foi contornado.
   Os hooks globais do usuário (`~/.claude/settings.json`) não entram, porque o `claude -p` da prova roda com
   `--setting-sources project,local`. O `init` do stream mostra `permissionMode: acceptEdits`. SUSPEITA não verificada:
   `find … | sort` passou sem estar na lista, provavelmente por ser um comando somente-leitura que a plataforma libera
   sozinha.
3. A medição desse despacho continua válida. O agente gravou Y (`DEPENDE_DE["poda"]` ∋ `"adubacao"`), e o
   `classify_dep` do arquivo salvo dá `Y`. Só o parser derrubou a rodada.

## O que muda
- **Parser:** `tool_events`/`read_stream` toleram `message` não-dict e linhas que não são objeto. Uma exceção ao medir
  um despacho vira **NOT_RUN** (`erro.txt`, fora do n e contado à parte no placar), nunca um traceback que derruba
  os outros despachos.
- **Negações:** `permission_denials()` classifica a origem em `permissao` (allow-list) ou `produto` (hook, cs-guard),
  pelo `tool_result` do mesmo `tool_use_id`. Grava `negacoes.json` por despacho, e o placar e o resumo contam as duas.
- **Allow-list mínima e explícita:** acrescenta `Bash(python3 *)`, `Bash(echo *)`,
  `Bash(git status|diff|log|show *)` e `Bash(<alvo>/.swarm/bin/cs-state|cs-mem *)` (caminho absoluto, por despacho).
  Continua sem `bypassPermissions`, e as regras para `.swarm/bin/*` relativas ficam como estavam.
- **Aborto cedo:** se o 1º despacho tiver Bash negado pela ALLOW-LIST, a rodada grava o placar parcial e para, sem
  gastar os outros 19. Uma negação só do cs-guard não aborta.
- **Sonda:** `--offline-check --sonda-api` (`--sonda-model haiku`, `--sonda-budget 0.2`) faz 1 despacho real pelo
  caminho do produto. O subagente roda `cs-mem search`, `python3 -m unittest …; echo "EXIT:$?"` e `git status`. A
  sonda passa se os três rodaram e nenhuma negação veio da allow-list.
- **M13 (requisito novo, D):** dado de uso real na segunda cobaia .NET.
  - (A) A MEMÓRIA do brief é cortada pelo orçamento quando o glossário é grande.
  - (B) `cs-mem check --agent X`, como o cartão e o brief mandam rodar, sai vazio.
  - (C) No empate de count, a lição antiga vem primeiro.
  Três testes D e um alvo `big` com mais 400 termos. Detalhes, critério e calibração estão no ESPEC (§M13).
- **Molde da prova na escala real** (`--termos`, padrão 400): o `sem-caderno` passa a medir o agente sem caderno
  exatamente pelo canal brief/check que A e B quebram. O offline-check confere a escala e mostra, como diagnóstico,
  que no HEAD a lição falta no brief ("omitidos pelo orçamento") e no check.

## Por que não enfraquece
- **Camada mecânica:** M1–M12 têm placar idêntico (D 0/33, R 19/19, nos 2 Pythons). Nenhuma asserção foi afrouxada.
  O M13 só acrescenta (D 0/3). O total fica em D 0/36, R 19/19.
- **NOT_RUN** fica fora do n, mas é contado e publicado. Um despacho quebrado não vira aplicação nem falha silenciosa.
- **Allow-list:** cresce o mínimo para o fluxo documentado (testes, cs-state, cs-mem, leitura do git). Nenhuma escrita
  nova de git e nenhum bypass. Hooks do produto continuam valendo e são medidos (`negado_produto`).
- O aborto cedo não muda nenhuma medida: só impede gastar uma rodada inteira em condição inválida.

## Verificação feita (na cópia de desenvolvimento, sem tocar os arquivos congelados)
- `medir.py` nos 2 Pythons: veja `base.txt` no patch (rc 0; 58 s e 59 s).
- `prova_real.py --offline-check`: 33/33 OK, sem API. O parser lê o `saida.jsonl` REAL da evidência sem erro: 57
  mensagens, 22 eventos, negações `[permissao: python3…; echo…, produto: cs-state verify]`, `early_abort = True`.
- `--offline-check --sonda-api`: 1 despacho haiku, rc 0. O subagente rodou cs-mem search, python3+echo e git status,
  sem negação da allow-list; o único bloqueio foi do cs-guard (`cs-state verify`, produto). Custo de US$ 0,207,
  ligeiramente acima do teto de 0,20: o `--max-budget-usd` do Claude Code é checado entre turnos.
