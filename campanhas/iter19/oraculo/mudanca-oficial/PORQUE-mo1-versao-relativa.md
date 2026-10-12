# PORQUÊ — mudança oficial 1 do oráculo iter19: versão relativa (B-32)

Classe: **defeito do ORÁCULO** (fixação de versão). O produto não muda. Os testes de versão comparavam por igualdade
com a versão da campanha; a cada subida de versão eles quebravam sem defeito nenhum (a cópia 0.12.0 da iter21 falha
só por isso). Regra do founder: "versão ≥ X e migração X presente no catálogo; README cita a VERSION corrente" —
nada de "versão == X".

- Patch: `campanhas/iter19/oraculo/mudanca-oficial/oraculo-iter19-mo1-versao-relativa.patch` (2 arquivos). Aplicar da raiz:
  `patch -p0 < campanhas/iter19/oraculo/mudanca-oficial/oraculo-iter19-mo1-versao-relativa.patch` (conferido com `--dry-run`, rc 0).
- sha256 antes → depois:
  - `ESPEC.md` b2d91a46142ab9f4892986e5d497767f83809218bb4b73649fa19ea6d8e263c8 → 3d6a5a2f32e7c1e1dffb721fdb18e809d9c52eabfe893287319773f193abf867
  - `test_iter19.py` a7db3d4db33670c6fcc8c9744174eda67636f8854331f758504073877088bd84 → 4eeed970947b5a86a0aeb0e9a36c04976c3435016c5d3b928ff676870f10b071
- `medir.py` e `base.txt` não mudam (a base é histórica). Nenhum `def` foi removido (0 linhas `-def`/`-    def` no patch);
  só entram helpers novos.

## O que muda
- `TestCA06`, só os dois testes de versão:
  - `test_ca06_version`: VERSION ≥ 0.11.0 (era `==`).
  - `test_ca06_catalogo_tem_a_0110`: `version` do catálogo = VERSION corrente e a última migração é a dela; `to:
    "0.11.0"` continua única, logo depois da 0.10.1 e com ações (a checagem de ações passa a olhar a entrada 0.11.0,
    não a última).
  - **Não mudam** (byte a byte): `test_ca06_catalogo_e_config_continuam_json5`, `test_ca06_eventos_continuam_jsonl_canonico`,
    `test_ca06_memoria_e_mandato_novos_continuam` e os demais do CA-06 — logs JSONL, config JSON5, memória do cs-mem e
    chaves do M5.
- Novo helper de módulo `vtuple(v)` e método `TestCA06.current()`.

## Por que não enfraquece
- Só a igualdade de versão vira "≥". A presença (e unicidade, ordem e ações) da migração X no catálogo continua exigida,
  e o catálogo e o README ficam AMARRADOS à VERSION corrente (antes, à X) — uma skill com VERSION, catálogo e README
  desencontrados continua reprovada.
- Nenhum outro teste foi tocado.

## Verificação feita (cópia temporária do oráculo com o patch; skills em cópia; nada congelado foi editado)
- HEAD (VERSION 0.11.0): 39/39 OK em python3 3.13 e /usr/bin/python3 3.9.
- Cópia de trabalho da iter21 (VERSION 0.12.0): 39/39 OK nos 2 Pythons.
- Mutações (cópia da skill 0.12.0, nos 2 Pythons): apaga 0.11.0 do catálogo → `test_ca06_catalogo_tem_a_0110` FAIL; apaga 0.10.1 → o mesmo teste ERROR (`index`); VERSION=0.10.0 → `test_ca06_version` e `test_ca06_catalogo_tem_a_0110` FAIL.
