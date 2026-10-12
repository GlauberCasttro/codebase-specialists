# PORQUÊ — mudança oficial 1 do oráculo iter20: versão relativa (B-32)

Classe: **defeito do ORÁCULO** (fixação de versão). O produto não muda. Os testes de versão comparavam por igualdade
com a versão da campanha; a cada subida de versão eles quebravam sem defeito nenhum (a cópia 0.12.0 da iter21 falha
só por isso). Regra do founder: "versão ≥ X e migração X presente no catálogo; README cita a VERSION corrente" —
nada de "versão == X".

- Patch: `campanhas/iter20/oraculo/mudanca-oficial/oraculo-iter20-mo1-versao-relativa.patch` (2 arquivos). Aplicar da raiz:
  `patch -p0 < campanhas/iter20/oraculo/mudanca-oficial/oraculo-iter20-mo1-versao-relativa.patch` (conferido com `--dry-run`, rc 0).
- sha256 antes → depois:
  - `ESPEC.md` 9e73028804d9757aa55ad11706e0cc288a63fe75140883fcc5e72e7034e733f2 → f9bfaf74587ad72879881af0bdb5c6fb3e3ab0fdcdecdd5c8c2b0aa0a27e6372
  - `test_iter20.py` eb146201ef9165099e566248cd4dc1accb71538687decf2a90c547640ad64b13 → bac3c2d0ebe07a209ee4ff07402b825e9ab1b9afc102bacd0c804f42c1bf0d40
- `medir.py` e `base.txt` não mudam (a base é histórica). Nenhum `def` foi removido (0 linhas `-def`/`-    def` no patch);
  só entram helpers novos.

## O que muda
- `TestU5Versao`: `test_u5_version` VERSION ≥ 0.10.1; `test_u5_migrations` catálogo na VERSION corrente, última
  entrada = VERSION corrente, `to: "0.10.1"` única, actions ⊇ {harness}, logo depois da 0.10.0 (mantido);
  `test_u5_readme` README cita a VERSION corrente (≥ 0.10.1). `test_u5_docs_upgrade` não muda.
- `TestU5DeZeroNoveDireto` (o caminho 0.9.0 → 0.10.0 → 0.10.1 continua provado):
  - plano: `versão do alvo:  0.9.0` (mantido), `versão da skill: <VERSION corrente>` (≥ 0.10.1),
    `migrações no intervalo (N)` com N = entradas do catálogo em (0.9.0, VERSION] (era 2 fixo), e as linhas `0.10.0 — `
    e `0.10.1 — ` continuam exigidas.
  - apply: `skill_version` = VERSION corrente; `upgrade_history[-1].from` = 0.9.0 (mantido); `migrations[:2]` =
    [0.10.0, 0.10.1] E a lista inteira = catálogo em (0.9.0, VERSION], em ordem (era [0.10.0, 0.10.1] fixo).
- Novos helpers de módulo `vtuple`, `current_version`, `expected_from_090`.

## Por que não enfraquece
- Só a igualdade de versão vira "≥". A presença (e unicidade, ordem e ações) da migração X no catálogo continua exigida,
  e o catálogo e o README ficam AMARRADOS à VERSION corrente (antes, à X) — uma skill com VERSION, catálogo e README
  desencontrados continua reprovada.
- Nenhum outro teste foi tocado.

## Verificação feita (cópia temporária do oráculo com o patch; skills em cópia; nada congelado foi editado)
- HEAD (VERSION 0.11.0): 24/24 OK em python3 3.13 e /usr/bin/python3 3.9.
- Cópia de trabalho da iter21 (VERSION 0.12.0): 24/24 OK nos 2 Pythons.
- Mutações (cópia da skill 0.12.0, nos 2 Pythons): apaga 0.10.1 do catálogo → `test_u5_migrations`, `test_u5_plano_de_090…` (falta a linha `0.10.1 — `) e `test_u5_apply_de_090…` (`['0.10.0','0.11.0'] != ['0.10.0','0.10.1']`) FAIL; apaga 0.10.0 → os mesmos três FAIL; VERSION=0.10.0 → `test_u5_version`, `test_u5_migrations`, `test_u5_readme` FAIL; README sem a VERSION → `test_u5_readme` FAIL.
