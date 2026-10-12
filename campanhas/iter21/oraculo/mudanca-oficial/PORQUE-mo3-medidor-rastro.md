# PORQUÊ — mudança oficial 3 do oráculo iter21 (sobre a mo2 aplicada)

Classe: **defeito do ORÁCULO** (medidor da prova real). Nenhuma asserção do `test_iter21.py` muda e o produto não muda.

- Patch: `campanhas/iter21/oraculo/mudanca-oficial/oraculo-iter21-mo3.patch` (2 arquivos). Aplicar da raiz do projeto:
  `patch -p0 < campanhas/iter21/oraculo/mudanca-oficial/oraculo-iter21-mo3.patch` (conferido com `--dry-run`, rc 0).
- sha256 antes → depois:
  - `ESPEC.md`      c5eea37b920821a11f1b26a0fb47c06983af00c73db032146621a0de553be6b7 → 5f05cb0ba2e27cdd8bf4c0da15ae6da980d03f3083be12936262e09fe18f28c2
  - `prova_real.py` 74d12c904352de7367b8fa11ef2d07c58219ab8efac47097440b45b2fba16f49 → 965d20eeb953325891a82fb927b27fe6f55d7476f711b002f6df157c98f3b4ec
- Nenhum `def` removido: o patch não tem linha `-def` nem `-    def`, e a assinatura de `score_search` fica igual.
  Entram `trail_new`, `trail_records`, `recount_baseline`, `recount_one`, `recount` e `--recontar`.

## Defeito
`score_search` filtrava `trail = [ln for ln in swarm_new.splitlines() if re.search(r"search", ln, re.I) and AGENT in ln]`.
O problema é que `swarm_new` vem de `new_text`: ele junta só o CONTEÚDO novo dos arquivos sob `.swarm/`, sem o nome do
arquivo. A linha do contrato B-24 (`PLANO.json5`, `rastro_busca`: `.swarm/state/memory/search.jsonl`, linha
`{at, agent, query, kinds, paths, hits, ids}`) não tem a palavra "search". Por isso `pesquisou_rastro` e
`tema_no_rastro` davam sempre False, e `coerente` dava 0 por construção para qualquer produto que seguisse o contrato.
Na config `pesquisa`, a aplicação depende de `coerente` e também dava 0 por construção.

Evidência: em `depois-r1/pesquisa/00` (rodada gravada), o `alvo/.swarm/state/memory/search.jsonl` traz
`{"agent":"dev-cultivo",…,"query":"calagem","ids":["gloss.calagem","decision.a757008dd90a",…]}`, e o `resultado.json`
da mesma execução marca `pesquisou_rastro: false` e `coerente: false`. O placar original mostra coerente 0 em todas as
configs de r0 e de r1.

## O que muda
1. O rastro passa a ser o ARQUIVO `.swarm/state/memory/search.jsonl`: só as linhas novas entre as fotografias, lidas
   pelo caminho (`TRAIL_REL`) e parseadas como JSON. Conta só a linha com `agent == AGENT`. Linha com `agent` null ou de
   outro agente não conta. `tema_no_rastro` = cada tema declarado é substring do `query` de alguma linha do agente (a
   mesma comparação exata de antes, agora feita no campo certo).
2. `--recontar DIR [--out OUT]` repontua uma rodada gravada sem API. A fotografia "antes" é o molde copiado para o alvo
   (`_molde-base`, `_molde-corrigido`, `_molde-refinado` ou `persistencia/_cadeia`). A pesquisa é recalculada e, só em
   `pesquisa`, a aplicação também. Entrega, classe e detecção vêm do `resultado.json`. A saída vai para
   `placar-recontado.json`, `resumo-recontado.md` e `recontagem.json`, sem sobrescrever o original.
3. O `--offline-check` ganha 6 casos (33 → 39):
   - a linha do contrato do próprio agente é coerente;
   - `agent` null não conta;
   - outro agente não conta;
   - o nome do agente só no texto da linha não conta;
   - um tema ausente das queries dá `tema_no_rastro` false;
   - só contam as linhas novas do arquivo, pelo caminho.

## Por que não enfraquece
- `coerente` continua exigindo tema declarado, tema no rastro (agora mais estrito: dono = campo `agent`, não um
  substring da linha) e ID saído do `tool_result` da busca. Ficaram de fora a busca sem dono (`agent` null) e as linhas
  de outros arquivos sob `.swarm/`.
- Os 33 checks antigos continuam verdes nos 2 Pythons. O caso sintético antigo (`trail_ok`) segue coerente porque é uma
  linha JSON do agente.
- Na recontagem de r0 e r1, a aplicação e a entrega das configs de dependência não mudaram em nenhuma execução. Só
  mudaram `coerente` e a aplicação de `pesquisa`, que deriva dele.

## Calibração (2 Pythons: python3 3.13 e /usr/bin/python3 3.9)
- `--offline-check`: 39/39 nos dois, rc 0. Sem o patch: 33/33.
- Recontagem (coerente original → recontado; aplicação original → recontada):
  - r0:
    - base 0→1; aplicação 0→0
    - depois 0→3; aplicação 3→3
    - sem-gatilho 0→3; aplicação 3→3
    - persistencia 0→1; aplicação 3→3
    - sem-caderno 0→3; aplicação 3→3
    - pesquisa 0→2; aplicação 0→2
  - r1:
    - depois 0→1; aplicação 3→3
    - pesquisa 0→3; aplicação 0→3
  - Pesquisou e declarou ficam iguais ao original em todas as configs.
- Casos conferidos à mão:
  - r1 pesquisa/00: a linha do agente tem query "calagem", o tema declarado é "calagem" e o ID `decision.a757008dd90a`
    está no `tool_result`. Resultado: coerente.
  - r0 pesquisa/00: a linha tem `agent: null` e query "calagem". Não conta, então não é coerente.
  - r1 depois/00: a query "irrigacao drenagem" bate com o tema, mas o ID `L-dev-cultivo-d566283b` não saiu do
    resultado da busca (`id_saiu_da_busca` False). Não é coerente.
  - r0 persistencia/02: a query "DEPENDE_DE" bate com o tema e o ID está no resultado. A fotografia "antes" é
    `_cadeia`, que já tinha 3 linhas; só as 2 novas contam. Resultado: coerente.
