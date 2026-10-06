# Por que mexer em dois oráculos congelados (só no COMO o approve é digitado)

**Arquivos:**
- `campanhas/m5/oraculo/test_mandato.py`
  (sha256 antes do patch: `aa87025f631ea04c6e18fb4b3d25d914e077f5fa6ec4d0bf274839ed1facecb9`)
- `codebase-specialists/scripts/harness/tests/test_cobertura_maquinas.py` (oficial; os cenários `m5_*` de
  `m5_cenarios.py` aprovam por `h.auto` → `_run`)
  (sha256 antes do patch: `6da187fa2547f05edee0aca1076844b0093e317cc141e354e51197b3ff2a24d1`)

**Patch:** `mandato-senha.patch`. Aplicar a partir de `~/.claude/skills/`:
`patch -p0 < campanhas/iter14/oraculo/mudanca-oficial/mandato-senha.patch`
(conferido com `patch -p0 --dry-run`).

## O conflito
A iter14 liga a senha de verdade: `cs-auto approve` só aprova com stdin tty + `/dev/tty` + a senha certa digitada
(ESPEC iter14 §2.2). Os dois oráculos aprovam mandatos rodando `cs-auto approve --by founder` como subprocesso SEM
terminal e passam a "prova humana" por `$CS_HUMAN_PROOF_ARGS` (argumentos extras). Contra um produto correto:
- sem terminal o approve falha → todo teste que aprova fica vermelho;
- `CS_HUMAN_PROOF_ARGS` não pode servir de saída: senha por argumento é exatamente o que a iter14 proíbe.
Sem o patch, implementar S2 deixa os dois oráculos vermelhos; mantê-los verdes impede S2.

## O que muda (só isso)
1. Um bloco de apoio (o mesmo nos dois arquivos): `senha_file()` grava UMA vez por processo, num diretório
   temporário fora do alvo, o registro PBKDF2 (formato §2.1) da senha de teste `Mandato-Seguro-2026`;
   `is_approve(args)` reconhece o subcomando `approve` (depois de `--root/--actor`); `run_tty()` roda o comando num
   pseudo-terminal REAL (`pty.fork`) e digita a senha a cada prompt `SENHA...:` — o mesmo método do
   `_pty_helper.py` da auto-correcao.
2. O ambiente de todo subprocesso ganha `CS_SENHA_FILE=<registro de teste>` (caminho; nunca a senha).
3. `_run`: quando o comando é `cs-auto approve`, roda via `run_tty`; stdout e stderr chegam juntos (é um terminal),
   então `out` e `err` recebem a mesma saída. Todo o resto segue por `subprocess.run` como antes, e a contabilidade
   (eventos novos, `guarda <nome>:` no stderr, observador SHIM) é a mesma.

## Por que não enfraquece nada
- **Nenhuma asserção muda.** Os mesmos testes aprovam, recusam (`by_human`, `acceptance_red`) e exigem os mesmos
  estados, eventos e guardas. A recusa por guarda continua sendo exit 1 com `guarda <nome>:` na saída real.
- **Nenhum bypass no produto:** o patch não cria variável que pule a senha. Ele faz o que o humano faz: digita a
  senha num terminal. A senha só vale porque o registro de teste foi gerado com ela.
- **Funciona antes e depois:** contra a skill atual (approve sem prompt) o pty só não vê prompt e o approve passa
  como antes; contra a implementação nova, digita a senha. Resultados em `../base.txt` (§ regressão).
- `$CS_HUMAN_PROOF_ARGS` continua lido pelo `_human_argv` do M5 (o patch não o remove), mas deve ficar vazio:
  com a senha ligada, argumento extra no approve é recusado.
- O `test_mandato_nunca_aprova_portao_humano` (guard bloqueando `cs-auto approve` do modelo) não é tocado.
