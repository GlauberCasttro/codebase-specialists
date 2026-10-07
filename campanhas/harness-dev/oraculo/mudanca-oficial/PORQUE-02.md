# PORQUE 02 — mudança oficial: "frente" vira "feature" no harness de desenvolvimento

Patch: `02-frente-para-feature.patch` (`patch -p1` a partir da raiz do projeto; `--dry-run` confere nos 2 arquivos).
Alvo: `campanhas/harness-dev/oraculo/test_harness_dev.py` e `ESPEC.md` (o oráculo congelado; a suíte em
`.claude/tools/tests/` é a cópia que o G3 mantém). Decisão do founder: renomear tudo de "frente" para "feature" no
harness (`.claude/`). Não aplicado; precisa de descongelar/re-congelar o oráculo pelo fluxo oficial.

## O que muda
Substituição mecânica e total, preservando maiúsculas: `frente`/`frentes`/`Frente`/`FRENTE(S)` para
`feature`/`features`/`Feature`/`FEATURE(S)`. "Fronteira" (classe e prosa) não contém "frente" e fica intacta, assim
como o motor `ac/**` ("front report", "-front" de new-front/close-front, que são nomes ingleses antigos de skill).

| item | antes | depois |
|---|---|---|
| skills | criar-frente, fechar-frente | criar-feature, fechar-feature (SKILLS, MUDAM_ESTADO, termos) |
| script | `frente.py` (+ `test_frente.py` na lista) | `feature.py` |
| arquivos/pastas | `FRENTE.md`, `frentes/`, `frentes.json` | `FEATURE.md`, `features/`, `features.json` |
| texto/chaves | `FRENTE-ID`, `Frente-ID`, "Aceite da Frente", `max_frentes_ativas`, `FRENTES:` (carimbo), `--frente`, subcomando `contrato.py frente`, marcadores `frentes:inicio/fim` | equivalentes com "feature" |
| identificadores Python | `FRENTE_OK`, `CriarFrente`, `FecharFrente`, `frentes_json()`, `fr()` usa `feature.py` | `FEATURE_OK`, `CriarFeature`, `FecharFeature`, `features_json()` |
| ESPEC | prosa, tabelas, grupos G1/G3 | idem; contagem 101 → 103 testes; CriarFeature 20 → 22 |

## Testes novos (compatibilidade): 101 → 103
Ambos em `CriarFeature`, nomes antigos montados por partes (`"fr"+"ente"`) para o arquivo não reintroduzir o termo.
1. `test_state_antigo_frentes_json_e_lido`: adota uma campanha, devolve o state a `frentes.json` + `frentes/`; `feature.py
   status --json` ainda lista a ativa (`velha`, origem `legado`, IN_PROGRESS).
2. `test_rotulos_antigos_lidos_e_reescritos_com_os_novos`: state com marcadores `frentes:inicio`, rótulo `**Frentes
   ativas:**`, `FRENTES:` no carimbo e `frentes.json`; `sessao.py frescor --json` lê sem erro; uma nova adoção preserva a
   ativa antiga, ESCREVE `features.json` e regrava o WORKFLOW com `features:inicio` (sem o marcador antigo).

## Contrato implícito para o corretor
Ler os dois nomes (preferir `features.json`; cair em `frentes.json`; idem `features/` vs `frentes/`, marcadores do
WORKFLOW, rótulos `**Frente ativa:**`/`**Frentes ativas:**` e `FRENTES:` do carimbo); escrever só os novos.
Não exigi, de propósito, que o state antigo seja apagado/migrado (o teste 2 só exige que o novo exista).

## Riscos / não coberto
- Citações históricas do founder no ESPEC (ex.: "o criar-frente é muito rico") foram renomeadas junto; só afeta prosa.
- O teste `test_nomes_antigos_de_skill_ausentes` não passa a banir `criar-frente`/`fechar-frente` (os scripts os citam
  por compatibilidade e o state/logs os guarda); se o founder quiser, é emenda à parte.
- `base.txt` (medição antes da correção) não foi alterado.
- A suíte nova não foi executada (o projeto ainda não tem `feature.py`); só `py_compile` e `patch --dry-run`.
