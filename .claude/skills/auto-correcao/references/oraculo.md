# O oráculo de uma frente

Primeira trava: **sem oráculo confiável, não há laço.** Aqui quase toda frente é um requisito NOVO (o produto
ainda não faz X), então não existe "saída boa conhecida" para calibrar (L15). O oráculo é um conjunto de testes de
aceite escritos por um agente **separado** de quem corrige.

## Como é um oráculo deste projeto (ex.: `campanhas/iter17/oraculo/`)

- `ESPEC.md`: decisão do founder que fixa o requisito; como o oráculo isola (cópia temporária, HOME temporário,
  variáveis `CS_*`/`GIT_*` removidas, nada pede senha); o **contrato** item a item (comandos, flags, saídas, exit
  codes) — de preferência em tabela V/F por item (L21).
- `test_<frente>.py`: unittest puro, stdlib, Python 3.9+, roda nos 2 Pythons de dentro da pasta. Projeto sob
  teste por `$CS_SKILL_DIR` (é o que o `portao.sh` passa) ou `$CS_PROJETO`. Recurso privado só por variável de
  ambiente — sem ela o teste PULA com motivo.
- `base.txt`: a rodada no produto atual (o que falha hoje prova o defeito/requisito).
- `mudanca-oficial/`: patch + PORQUE de cada `oracle change`.

Nada privado (o repositório é público): pessoa = "Ana"; cobaia = "repositório-piloto (projeto-legado)" ou
"cobaia .NET"; caminhos com `~` ou variável. `bash .claude/tools/guard-privacidade.sh campanhas/<frente>` vazio.

## Calibração em modo requisito

| Clássica (L01) | Modo requisito (L15), o usual aqui |
|---|---|
| saída vazia ≈ 0 | `base.txt`: no produto atual, 0% dos testes do requisito passam (os de regressão, se houver, passam) |
| saída boa conhecida passa | o founder confere os testes × ESPEC e aprova `gate oracle:requisito` (no script dele) |
| ≥ 2 asserções conferidas à mão por configuração | você confere à mão ≥ 2 testes (um que deve falhar hoje e por quê) e registra a evidência |

Grave: `python3 .claude/tools/ac/ac.py --work campanhas/<frente> set oracle.calibration '<json>'` (formato em
`ac/references/formatos.json5` e no check `calibration`). Sistema com estados (máquina de estado, mandato,
delegação): o oráculo tem teste de **vivacidade** (nenhum estado sem saída acidental) e um ponta a ponta que
percorre os desvios (L16).

## Congelar e mudar

- `oracle freeze --file <cada arquivo>` — TODOS os arquivos, inclusive auxiliares. Só o que está em `--file` é
  protegido pelo hash e pelo `plan check`.
- `oracle verify` na integração: hash diferente ⇒ descubra quem tocou antes de qualquer coisa.
- `oracle change --why "<erro do oráculo>" --evidence "<conferência à mão: arquivo:linha>" --file <TODOS>` — só
  com evidência de que o ORÁCULO erra (defeito de classe `oraculo`), nunca para fazer passar. `--file` SUBSTITUI a
  lista inteira: passe todos. Grave patch + PORQUE em `mudanca-oficial/`. Toda medição anterior é recorrigida.
- AC-08 (aberto): `oracle change` re-hasheia o disco e absorveria uma edição indevida — confira o diff dos arquivos
  desde o freeze antes de rodar.

## Sinais de que o oráculo mente

Teste que só passa com o formato da própria saída do produto · negação lida como afirmação · nome de campo
divergente · a mesma grandeza medida de dois jeitos · reprovação vinda do ambiente da prova (sem `.git`, sem
termo privado) · teste que exige "passa sem evidência" (L22). Classifique como `oraculo` no diagnóstico e trate
por `oracle change`, fora das frentes de correção.
