# PORQUÊ — mudança oficial 1 do oráculo iter18: versão relativa (B-32)

Classe: **defeito do ORÁCULO** (fixação de versão). O produto não muda. Os testes de versão comparavam por igualdade
com a versão da campanha; a cada subida de versão eles quebravam sem defeito nenhum (a cópia 0.12.0 da iter21 falha
só por isso). Regra do founder: "versão ≥ X e migração X presente no catálogo; README cita a VERSION corrente" —
nada de "versão == X".

- Patch: `campanhas/iter18/oraculo/mudanca-oficial/oraculo-iter18-mo1-versao-relativa.patch` (2 arquivos). Aplicar da raiz:
  `patch -p0 < campanhas/iter18/oraculo/mudanca-oficial/oraculo-iter18-mo1-versao-relativa.patch` (conferido com `--dry-run`, rc 0).
- sha256 antes → depois:
  - `ESPEC.md` d33bc38bf4d845f9d719ea8a1ee0425120c8f25f21acba5e2bcaa2765363f18b → c09f41f4f47e6ef12919abd13e277be82ba6ce13d12dd36965ba1c5cc8544913
  - `test_iter18.py` df33eca0623e23c44b8796fcdee44f9d80d465db2a79c18582809e2bf039853f → 268ddbb3745779233699bcec15f5b3134e1557adb9046933ab8cd64d3e9405e7
- `medir.py` e `base.txt` não mudam (a base é histórica). Nenhum `def` foi removido (0 linhas `-def`/`-    def` no patch);
  só entram helpers novos.

## O que muda
- `TestR8Versao` (fixava `V = "0.10.0"` por igualdade):
  - `test_r8_version`: VERSION ≥ 0.10.0 (era `==`).
  - `test_r8_migrations`: VERSION ≥ 0.10.0; `migrations.json5.version` = VERSION corrente; a migração `to: "0.10.0"`
    continua única e com actions ⊇ {harness, emit}; a última migração é a da VERSION corrente (era: a última é 0.10.0).
  - `test_r8_readme`: VERSION ≥ 0.10.0 e o README cita a VERSION corrente (era: cita 0.10.0).
  - `test_r8_docs_upgrade` não muda (o título `Migração 0.10.0` continua exigido).
- Novo helper de módulo `vtuple(v)` (comparação por tupla de inteiros).

## Por que não enfraquece
- Só a igualdade de versão vira "≥". A presença (e unicidade, ordem e ações) da migração X no catálogo continua exigida,
  e o catálogo e o README ficam AMARRADOS à VERSION corrente (antes, à X) — uma skill com VERSION, catálogo e README
  desencontrados continua reprovada.
- Nenhum outro teste foi tocado.

## Verificação feita (cópia temporária do oráculo com o patch; skills em cópia; nada congelado foi editado)
- HEAD (VERSION 0.11.0): 38/38 OK em python3 3.13 e /usr/bin/python3 3.9.
- Cópia de trabalho da iter21 (VERSION 0.12.0): 38/38 OK nos 2 Pythons.
- Mutações (cópia da skill 0.12.0, nos 2 Pythons): apaga 0.10.0 do catálogo → `test_r8_migrations` FAIL; VERSION=0.10.0 numa skill 0.12.0 → `test_r8_migrations` e `test_r8_readme` FAIL (catálogo/README fora da VERSION); README sem a VERSION → `test_r8_readme` FAIL. Apagar 0.10.1 ou 0.11.0 não afeta o R8 (correto: não é dele).
