# PORQUÊ — mudança oficial 2 do oráculo iter19: épico grava `kind: "epic"` (iter26, CA-02, D-41)

Classe: **evolução aprovada do produto** (decisão do founder, 2026-10-17, "sim os dois"). Na 0.14.0 (iter26, CA-02
aprovado) o épico novo grava `kind: "epic"` no disco; "epico" continua lido. `test_ca01_entidades_e_sessao_sao_json`
exigia a palavra antiga "epico" entre os kinds da fixture. O teste continua provando o mesmo (toda entidade em .json,
estrito, e a fixture com todos os tipos); só passa a aceitar `epic` como o épico.

- Patch: `campanhas/iter19/oraculo/mudanca-oficial/oraculo-iter19-mo2-kind-epic.patch` (1 linha, 1 arquivo). Aplicar da raiz: `patch -p0 < campanhas/iter19/oraculo/mudanca-oficial/oraculo-iter19-mo2-kind-epic.patch`.
- sha256 de `test_iter19.py`: 4eeed970947b5a86a0aeb0e9a36c04976c3435016c5d3b928ff676870f10b071 → 5eb5c5a49005f597fe5a66c839f27b38cecb1d4c4a43768b527d334fe8c7daba
- `ESPEC.md`, `medir.py`, `base.txt` não mudam. Nenhum `def` removido.
- Evidência: com o patch, `test_iter19` OK (39) em python3 e /usr/bin/python3 contra a cópia da iter26 e contra o HEAD
  bac0e0f (0.13.1).
