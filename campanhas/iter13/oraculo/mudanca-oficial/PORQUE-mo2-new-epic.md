# PORQUÊ — mudança oficial 2 do oráculo iter13: a skill new-epic cita `new epic` (iter26, CA-04, D-44)

Classe: **evolução aprovada do produto** (decisão do founder, 2026-10-17, "sim os dois"). Na 0.14.0 os textos emitidos
citam `cs-state new epic`; `new epico` segue aceito como alias depreciado. `TestR1EmitSkillsMultiplataforma` exigia o
literal `new epico` no corpo da skill new-epic das 4 plataformas. O teste segue exigindo o comando real; o subcomando
esperado passa a ser `new epic` (que também casa `new epico` como substring, logo a 0.13.1 continua verde).

- Patch: `campanhas/iter13/oraculo/mudanca-oficial/oraculo-iter13-mo2-new-epic.patch` (1 linha). Aplicar da raiz: `patch -p0 < campanhas/iter13/oraculo/mudanca-oficial/oraculo-iter13-mo2-new-epic.patch`.
- sha256 de `test_menores.py`: bbb50e13b98b544aca637426dddf349867a855698acf78c1c71d23c86ed1c963 → 6fb29ea9f13b46a40cd83327955e790ee9a271afd4dfa0975719eb07f8fbb723
- `ESPEC.md` e `base.txt` não mudam. Nenhum `def` removido.
- Evidência: com o patch, `test_menores` OK em python3 e /usr/bin/python3 contra a cópia da iter26 e contra o HEAD bac0e0f.
