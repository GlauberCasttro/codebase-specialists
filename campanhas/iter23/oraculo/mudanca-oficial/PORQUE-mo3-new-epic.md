# PORQUÊ — mudança oficial 03 do oráculo iter23: `new epic` é o subcomando canônico (iter26, CA-04, D-43)

Classe: **evolução aprovada do produto** (decisão do founder, 2026-10-17, "sim"). Na 0.14.0 (iter26, CA-04 aprovado)
os textos emitidos citam `cs-state new epic`; `new epico` segue aceito como alias depreciado.
`test_ca07_todo_comando_citado_executa_na_arvore` só conhecia a chave ("new","epico") no mapa de comandos concretos e
acusava `new epic` como "não é comando do modo árvore". O teste continua exigindo que todo comando citado execute na
árvore; só passa a reconhecer `new epic` (mesma execução de `new epico`).

- Patch: `campanhas/iter23/oraculo/mudanca-oficial/oraculo-iter23-mo3-new-epic.patch` (1 linha, 1 arquivo). Aplicar da raiz: `patch -p0 < campanhas/iter23/oraculo/mudanca-oficial/oraculo-iter23-mo3-new-epic.patch`.
- sha256 de `test_iter23.py`: c951a92af7ee57c12dc8762c38da3df1f7e366764ed29be91faf6e55ac3f55b9 → ddd8b17a21e4852d0167fd1eaf248426802e5e97e3771672d1e3e197207fe943
- `ESPEC.md`, `medir.py`, `base.txt` não mudam. Nenhum `def` removido.
- Evidência: com o patch, `test_iter23` OK em python3 e /usr/bin/python3 contra a cópia da iter26 e contra o HEAD bac0e0f.
