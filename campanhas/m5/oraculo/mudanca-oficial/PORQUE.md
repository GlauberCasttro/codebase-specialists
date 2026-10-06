# PORQUE — mudança oficial nos oráculos congelados para a M5 `mandato`

**O que é:** `m5-cobertura-vivacidade.patch`. Aplique a partir de `~/.claude/skills/` com
`patch -p0 < campanhas/m5/oraculo/mudanca-oficial/m5-cobertura-vivacidade.patch`.
O patch altera `scripts/harness/tests/test_cobertura_maquinas.py` e `test_maquinas_vivacidade.py` e cria
`scripts/harness/tests/m5_cenarios.py`.

**Por quê:** o desenho (AUTONOMIA-DESENHO §5) põe a M5 em `machines.machines` para que ela passe pela checagem de
vivacidade e de alcançabilidade. Essa checagem existe por causa do bug real da delegação ESCALATED trancada. O founder
(D6) exige que o autônomo novo nasça com cobertura de 100%. Os dois oráculos congelados leem o universo em tempo de
execução. Por isso, com a M5 dentro de `machines`, o `test_cobertura_maquinas` passaria a exigir arestas e guardas da
M5 que nenhum cenário dele exercita. Tirar a M5 de `machines` contornaria o oráculo. A saída correta é estendê-lo.

## O que muda (só acréscimos; nenhuma asserção existente afrouxa)
| Arquivo | Mudança | Por que não enfraquece |
|---|---|---|
| vivacidade | `edges()` expande `to: "^"` (volta ao estado de origem) para os estados que levam à origem | Antes, `"^"` virava um "estado" fantasma. Para as máquinas antigas o resultado é idêntico, porque nenhuma usa `^` |
| vivacidade | teste novo `test_mandato_m5_presente_e_espera_nunca_tranca`: a M5 existe; AWAITING_HUMAN e PAUSED nunca são terminais e têm saída; AWAITING_HUMAN sai para RUNNING, PROPOSED, WRAPPING_UP e ABORTED | Só acrescenta. Os testes genéricos (sem beco, alcançável) passam a valer também para a M5 |
| cobertura | `universe()`: transição com `from: []` (criação, `mandato.propose`) gera a aresta `(m, t, None)` | Nenhuma transição existente tem `from` vazio, então o universo antigo fica igual (128/128 e 78/80 inalterados) |
| cobertura | `_account`: a aresta com `"^"` conta quando o destino gravado é um estado da máquina | Mesma exigência das outras: evento gravado e avaliação sem problema |
| cobertura | recusa INTERNA: o Refused é capturado pelo motor e gravado em `data.guardas_recusadas` do evento vencedor | Exige a guarda real (observada pelo shim) e o registro dela no evento. É o equivalente do caso `on_guard_fail` que já existia |
| cobertura | criação: aresta pelo evento; guarda OK por `data.guardas`; recusa por exit 1 com `guarda <nome>:` no stderr, sem recusa de outra máquina | Não existe entidade antes, então o shim não consegue observar `engine.evaluate`. Só se aplica a `from: []` |
| cobertura | `H.auto` (CLI `cs-auto`, observada) e `H.hook(..., env_extra)` | Mesmo `_run` com o mesmo shim |
| cobertura | 14 cenários `m5_*` (em `m5_cenarios.py`) registrados no mesmo `SCENARIOS` | Rodam pela CLI e pelos hooks reais, como os demais |
| cobertura | `EXCLUSOES_M5` (14 chaves, só "guarda_recusa") entram **apenas** se `machines.mandato` existir | Cada uma tem motivo (guarda calculada pelo próprio motor, sem caminho legal de recusa). Sem a M5 não há chave obsoleta |
| cobertura | `TestM5Presente`: `machines.mandato` existe | Requisito novo |
| cobertura | impressão do resumo com `str()` e `sorted(key=str)` | Necessário por causa da aresta com `None`. É só formatação |

## O que fica exigido do produto (ESPEC §2.2)
- **Transições:** toda transição da M5 com entidade passa por `engine.transition`, com `hcore.KIND_MACHINE[kind] == "mandato"`.
- **Guardas:** as guardas ficam registradas em `engine.GUARDS`, e o problema de cada recusa vai para o stderr.
- **Recusa interna:** quando uma alternativa é recusada, o `Refused` é capturado e a recusa é gravada em `data.guardas_recusadas`.
- **Criação:** `propose` grava `data.guardas` no evento e imprime `guarda X:` no stderr quando recusa.

## Medido (detalhe em `../base.txt`, seção B)
- **Código atual, sem o patch:** 128 testes OK.
- **Código atual, com o patch:** 144 testes. Os 128 antigos seguem OK e `test_cobertura_100` não muda (78/80, 113/115, 71/71, 71/71). Só os 16 testes novos de M5 falham, porque o produto ainda não existe.
- **Com o patch e a M5 do ESPEC §2.1 injetada:**
  - A vivacidade passa 4/4.
  - Duas M5 quebradas são reprovadas: uma com AWAITING_HUMAN terminal e outra sem emendar/abortar.
  - Na cobertura, todas as 157 lacunas são `mandato/*`. Nenhuma outra máquina perde cobertura e não aparece exclusão obsoleta nem aresta fora do universo.
