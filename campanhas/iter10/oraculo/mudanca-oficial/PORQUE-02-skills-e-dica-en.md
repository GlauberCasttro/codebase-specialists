# PORQUÊ — mudança oficial 02 do oráculo iter10: flags en canônicas nas skills e na dica do guard (iter26, CA-04, D-45)

Classe: **evolução do produto decidida pelo founder** (2026-10-17, "sim"). Na 0.14.0 a CLI e os textos emitidos citam só
as flags em inglês (`--type`, `--as-a/--i-want/--so-that`, `--reason`, `--failing-test`, `new epic`); as pt seguem
aceitas como alias depreciado. Seis testes (TestGuard dica mínima; TestSkillsEmitidas dry-run, 14 skills, CHORE, DoR
por tipo, skills finas) exigiam o literal em pt. Onde o teste exige a flag/palavra pt, passa a aceitar também a
equivalente en (HINTS, FLAG_EN, `new epic` que casa `new epico`). O que cada teste prova não muda.

- Patch: `campanhas/iter10/oraculo/mudanca-oficial/02-skills-e-dica-en.patch` (11 linhas). Aplicar da raiz:
  `patch -p0 < campanhas/iter10/oraculo/mudanca-oficial/02-skills-e-dica-en.patch`.
- sha256 de `test_estado_arvore.py`: e78544480f8a094fba7ae1132cf15cf6a2427a03de52dee9ed61341ec4796660 →
  c283c9b5ea6d562d9f8f863e7633ec49646c54a53f8554788f3a0e4916c24042
- `ESPEC.md`, `test_upgrade_u1_u2.py`, `base.txt`, `legacy_flat/` não mudam. Nenhum `def` removido.
- Evidência (D-35, por nome de teste): contra a cópia da iter26, 0 testes que passam no HEAD falham, em python3 e
  /usr/bin/python3; contra o HEAD bac0e0f, as mesmas 21 falhas pré-existentes (B-61) antes e depois do patch.
