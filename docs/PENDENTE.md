# codebase-specialists — o que falta (atualizado em 2026-10-05, pausa por custo)

Versão publicada: **0.7.0** (`3127bf9`). As campanhas ficam em `campanhas/`.
Todas as campanhas seguem o método auto-correcao. `ac.py` = `python3 ~/.claude/skills/auto-correcao/scripts/ac.py`.

---

## 1. M5 — modo autônomo "mandato" (campanha-m5) · PRIORIDADE 1
**Estado:** o código está construído e o founder aprovou (com a senha). Os agentes mediram test_mandato 52/52 e vivacidade+cobertura 67/67 nos 2 Pythons. **O portão completo ainda não rodou**: o shell cortou em 30 min.

**Não commitado (é desta frente):**
- `scripts/harness/engine/auto.py` (novo), `cmds.py`, `engine.py`, `guard.py`, `hcore.py`, `tree.py`, `validate.py`;
- `scripts/harness/machines.json5`, `scripts/harness/install.py`, `scripts/harness/templates/cs-guard.sh`;
- `scripts/harness/tests/test_cobertura_maquinas.py`, `test_maquinas_vivacidade.py` e `m5_cenarios.py` (novo). São mudança OFICIAL do oráculo (patch do autor) e já estão registradas no ledger;
- `scripts/emit/platforms.py` (AUTO_SKILLS);
- `assets/templates/feature-autonoma.md`, `orchestrator.md` e `assets/templates/state/auto-*.md` (9 skills novas).

**Falta, em ordem:**
1. Portão em cópia limpa (HEAD + só os arquivos acima, e um link para `campanhas` ao lado da cópia), **uma suíte por vez**, para caber em 30 min.
   Rodar: oráculo `campanha-m5/oraculo/test_mandato.py` + `scripts/*/tests` nos 2 Pythons + conferir que nenhuma função foi removida e que `machines.json5` só ganhou `mandato`.
2. Frente de doc: seção "Modo autônomo" no `MODO-DE-USO.md`/`SKILL.md` (o fluxo `cs-auto propose → /auto-approve → tick … → report`, o que é do humano, orçamento e corte aos 80%); `VERSION` 0.8.0; entrada 0.8.0 em `references/migrations.json5` com as ações harness + emit.
3. Revisar 3 decisões que o construtor tomou além da ESPEC:
   - a revisão final vira um evento de dado;
   - um arquivo comum idêntico entre sub-ondas não reprova;
   - um nó travado por regressão de outro não fecha sozinho.
4. Fechar a campanha:
   - `ac.py --work .../campanha-m5 front report mandato|emissao --file …`;
   - `done correcao`, `set integration.tests_green true`, `done integracao`;
   - commit SÓ dos arquivos acima;
   - `run record --decision GO`, `done remedicao`;
   - o founder roda `ac.py --work .../campanha-m5 frase conferir`;
   - `done decisao`.

## 2. iter12 — upgrade em uso real (o que travou no repositório-piloto) · PRIORIDADE 2
**Estado:** o founder aprovou e o plano está fechado. A correção **não começou**. Ela espera o commit do M5, porque as duas frentes mexem em `selftest.py`.
**Diagnóstico** (detalhe com arquivo:linha em `campanha-iter12/oraculo/ESPEC.md`):
- **U-5 (causa da falha):** o `team.json5` preservado cita `.specialists/bin/cs-mem`. O emit copia esse caminho, a passada de resíduo do rename-dir reescreve os emitidos, o hash muda e o G7 do `emit validate` falha. **Correção:** traduzir os caminhos legados do `team.json5` ANTES do emit.
- **U-3:** o motivo da falha vai só para o stderr e o `_tail(n=8)` o corta. **Correção:** imprimir o comando e a saída da verificação que falhou.
- **U-4:** `harness selftest` num alvo ainda legado grava `.swarm/state/selftest.json5`, e isso bloqueia o próximo upgrade. **Correção:** não gravar em `.swarm/` quando o alvo é legado.

**Falta:**
1. Despachar o corretor (escopo: `scripts/upgrade/{core,version,cli}.py`, `scripts/emit/{core,render,validate}.py`, `scripts/harness/engine/selftest.py`, `scripts/cs.py`).
2. Oráculo: `campanha-iter12/oraculo/test_upgrade_real.py` (16 testes; copia o repositório-piloto real para tmp a cada execução).
3. Portão, commit e `frase conferir`.
4. Só então rodar o upgrade de verdade no repositório-piloto (backup em `backups/repositorio-piloto-2026-10-05/`).

## 3. iter11 — medição real (campanha-iter11) · PRIORIDADE 3
**Estado:** 26/29 do oráculo verdes.
**Não commitado (é desta frente):**
- `evals/check_run.py` e `evals/reference/` (novo);
- `scripts/facts/{cli,spotcheck}.py`, `scripts/panel/{cli,core}.py`, `scripts/probes/{cli,exam}.py`, `scripts/team/{cli,roster}.py`;
- `scripts/probes/tests/test_iter3_refine.py` (mudança oficial).

**Falta:**
1. Texto em `references/prompts.json5` (linhas ~16, 316, 318) e `references/stages.json5:58`: "gravar no `answer_file`; `probes check <a>` sem `--answers`".
2. Os 2 testes do sanitize da família B dependem de execuções reais em `runs/`.
3. Medição ENXUTA, decidida pelo founder: 1 execução `--fast` por fixture (py-billing, ts-shop, go-polyglot) para calibrar o custo em tokens. Só com esse número decidir se mede mais. O plano completo está em `campanha-iter11/oraculo/ESPEC.md` e custa ~6–9 h e 15–38 M tokens.
4. Portão, commit e `frase conferir`.

## 4. Versão pública (pedido do founder)
**Estado:** um agente monta `~/Repositorios/codebase-specialists` a partir da 0.7.0. A montagem tira os docs internos e as referências privadas, e acrescenta README, LICENSE MIT, .gitignore e um commit local.
**Falta:**
1. Conferir o grep de privados (`.claude/tools/guard-privacidade.sh`, tem de voltar vazio) e as suítes (nenhuma falha).
2. Publicar como `GlauberCasttro/codebase-specialists`, público, MIT: `gh repo create GlauberCasttro/codebase-specialists --public --source . --push`.
3. Depois do M5 e da iter12, atualizar o repositório público para a 0.8.0, repetindo a limpeza.

## 5. Menores
- Emitir as 14 skills de estado e as 9 do mandato também para Cursor, Copilot e Codex. Hoje só o Claude Code recebe.
- `reroute`/`retry` não atualizam `route`/`agent` no arquivo da task da árvore (risco anotado pelo construtor da iter10).
- `cs.py init` ainda cria o board legado: o alvo só vira árvore depois de `cs-state init` ou de `migrate`. O teste congelado `test_swarm_dir` exige isso, e a mudança tem de ser oficial.
- O repositório-piloto: o founder prefere testar primeiro num app novo. Depois da iter12: upgrade, destravar KEY/AGT e OPS/AGT/QA.
- Atualizar `docs/PONTOS-DO-FOUNDER.md` (checklist) com o que entrou em 0.7.0/0.8.0.
