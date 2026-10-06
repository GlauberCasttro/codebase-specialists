# Mudança oficial de oráculo: test_autonomy_install.py (iter11, sanitização)

Arquivo: codebase-specialists/scripts/harness/tests/test_autonomy_install.py
sha256 antes: ef2cdcc34e2e3fbb00a442fac9a837b7c70589a3fb151bd1c8e16069e8be95c3

## Conflito
Linha 159 (test_install_merge_makefile_selftest) exige `settings.json.bak-*` em `<root>/.claude/`.
Novo requisito iter11: instalação/upgrade não deixa arquivo solto fora de `.swarm/` e do manifesto.
install.py:237 passa a gravar o backup em `<alvo>/.swarm/backups/settings/settings.json.bak-<ts>`.
A asserção antiga codifica exatamente o comportamento a ser removido (backup ao lado do settings.json).

## O que muda
Só essa asserção, por duas:
1. assertTrue: existe `settings.json.bak-*` em `<root>/.swarm/backups/settings/` (listdir falha se o diretório não existir).
2. assertFalse: não existe nenhum `settings.json.bak-*` em `<root>/.claude/`.

## Por que não enfraquece
- O backup continua obrigatório (1): só muda o local, e o local é verificado por existência do diretório e do arquivo.
- Adiciona uma negativa (2) que a versão antiga não tinha: o vazamento em `.claude/` passa a reprovar.
- Implementação antiga reprova (1) e (2); nenhuma implementação que omita o backup ou o deixe em `.claude/` passa.
- Nenhuma outra linha do teste foi tocada.
