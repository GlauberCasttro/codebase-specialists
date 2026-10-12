# PORQUÊ — mudança oficial 2 do oráculo iter21 (sobre a mo1 aplicada)

Classe: **requisito novo de uso real** (M14, M15). Nenhuma asserção antiga muda; o produto não muda.

- Patch: `campanhas/iter21/oraculo/mudanca-oficial/oraculo-iter21-mo2.patch` (4 arquivos). Aplicar da raiz do projeto:
  `patch -p0 < campanhas/iter21/oraculo/mudanca-oficial/oraculo-iter21-mo2.patch` (conferido com `--dry-run`, rc 0).
- sha256 antes → depois (o "antes" é o "depois" da mo1):
  - `ESPEC.md`       b6c258714973770057418ad796be43e364a4c2bf9244700da248e2884fcfe0ec → c5eea37b920821a11f1b26a0fb47c06983af00c73db032146621a0de553be6b7
  - `base.txt`       127f2a68c319d3facaec826de1ffb2f2014e86571830eba50915a1154845c695 → 5a7de68db35cb420e736374cbaba93c08cfadcea047b3a204f610804195a6b41
  - `medir.py`       227bd43abd6a0c5ba0e75ad6b21cdad939e1a26d5b7f9238b98f77887dd6dde5 → b6a36ce064390ada067a181b7e068190072dc7aff2aa15c051c79f79853c9519
  - `test_iter21.py` 805a9a9474d77c4b55ad4027d68bca7879d7d71c3943240d4e7aa34dfd95883b → 9d83fb70ad13386befbe0d23d7bf6b6cbcaf7e09006979d661849943c079ffbb
- Nenhum `def` removido (o patch não tem linha `-def`/`-    def`). `prova_real.py` não muda.
- `medir.py`: só `ORDER` vai de `range(1, 14)` a `range(1, 16)` (placar com M14 e M15).

## Evidência
1. **F1 (CONFIRMADO por leitura do produto do HEAD):** `scripts/memory/mem.py` `add_lesson` soma `count` na 2ª correção
   parecida e chama `_promote` quando `count >= LESSON_PROMOTE_COUNT` (status `promoted`, proposta pendente).
   `inject_lessons` e `check` só leem `status == "active"`. Rodado contra o HEAD: depois de 2 `correct` iguais, `inject`
   sai `<<DADO lições de dev-cultivo>>\n<</DADO>>` (vazio) e, depois de 3, o `check --files` também. A lição some
   justamente quando o agente provou que a esquece: contradiz o objetivo "corrigido, memória atualizada, não esquece".
2. **Redação diferente do certo (dado do ciclo 2, avaliado):** corrigir o MESMO errado 3× com o certo reescrito virava
   3 lições de count 1 (alegação do revisor; não reproduzida aqui no produto do corretor, que não li). **É requisito de
   uso:** o dono corrige o mesmo erro com palavras diferentes; o sinal "o agente repetiu o erro" é do ERRO (`--wrong`),
   não da redação do certo. Se a contagem zera a cada redação, a reincidência nunca fica visível, e "não esquece mais"
   não é verificável. Vira `test_m14_reincidencia_sobrevive_ao_certo_reescrito`: a vigente é a última redação (F6) e a
   linha dela mostra reincidência 3.

## O que entra
- **M14** (`TestM14Reincidencia`, 5 D + 1 R): F1 (2× e 3× continuam no inject/check/brief/bloco; mesmo id; count 2 e
  reincidência visível na linha da lição) e F6 (certo novo para o mesmo errado substitui, não funde; e herda a
  contagem). Contrato mínimo da contagem no ESPEC: `N×`/`N vezes`/`reincidência: N`/`reincidente ×N`.
- **M15** (`TestM15CadernoEditadoDeVerdade`, 3 D): F4 (caderno CRLF: commit passa — dono no Windows/autocrlf seria
  barrado sem ter adulterado nada) e F5 parcial (BOM e marcador de fim apagado: um único bloco, nota do agente
  preservada uma vez). É outro requisito (robustez do arquivo editado), por isso não está no M14.

## O que fica de fora (e por quê)
- **F2** (retract/supersede e a proposta pendente): o comportamento certo é ambíguo (descartar a proposta de uma lição
  retratada é o esperado; transferi-la à refinada também é defensável), e o ESPEC não tem CLI que mostre propostas ao
  dono. O que o dono percebe — a lição retirada não ser mais injetada — já é o M12.
- **F3** (`cs-mem notebook --check` distingue desatualizado de adulterado): diagnóstico de CLI nova, não fixada no
  ESPEC; o efeito de uso (adulterado barrado, regenerado aceito) já é o M5. Sem cenário observável de "selo íntegro e
  desatualizado" sem conhecer o formato interno do selo.
- **F5, parte** (marcador `cs-mem` na área livre acusado): o canal da acusação (pre-commit? guard? check?) não é
  definido; fixá-lo seria ditar implementação.
- **F7** (decaimento por nº de tasks lendo projeção/board): depende de `DECAY_TASKS` e do formato interno do board; o
  decaimento observável já é o M2 (por data).
- **F8** (search imprime mesmo sem rastro; `--dry-run` não move arquivos): falha de rastro é condição rara de
  ambiente; o "prévia não grava" já é o M12.

## Por que não enfraquece
- M1–M13 com placar idêntico com e sem o patch, nos 2 Pythons (19/55; D 0/36, R 19/19), por `diff` das linhas de
  resultado. Contra o HEAD os novos dão M14 D 0/5 R 1/1, M15 D 0/3: total 20/64 (ver `base.txt`).
- As falhas no HEAD são por asserção (caderno ausente; lição sumida do inject/check), não por ImportError nem fixture.
- O controle `test_m14_correcao_unica_no_check_controle` passa no HEAD: prova que o `check` usado mede a lição.
