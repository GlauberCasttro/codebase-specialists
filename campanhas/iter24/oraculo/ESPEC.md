# Oráculo iter24 (0.12.2) — guard sem portas laterais

Exercita o guard INSTALADO num alvo (fixture do emit: init + harness install + emit) pelo hook real
(`CLAUDE_PROJECT_DIR=<alvo> python3 <alvo>/.swarm/harness/guard.py pre-bash|pre-write`). Atores:
principal (payload sem `agent_id`) e subagente `dev-billing` (`agent_id`/`agent_type`) com delegação DISPATCHED
real (task avulsa US, `cs-state start`, hook `pre-agent` com `<id>.d1` na description); allowed_path
`src/billing/coupons.py`. Os comandos sondados NÃO são executados; só o veredito do guard (exit 2 = recusa, 0 = libera).

Tipo: D = defeito (falha no HEAD da30e17/0.12.1, passa com a entrega); R = controle (passa sempre; nome com
`controle|continua`). Versão sempre relativa (≥).

| CA | Teste | Tipo | Critério |
|---|---|---|---|
| CA-01 | test_ca01_subagente_formas_indiretas_do_harness_recusadas | D | sub: `sh <bin> waive-verify`, `bash <bin> accept`, `python3 -W ignore …/state.py submit --task <alheia>`, `cd .swarm/harness && python3 -m state waive-verify` ⇒ 2 |
| CA-01 | test_ca01_principal_ato_humano_formas_indiretas_recusado | D | principal: `python3 -m state waive-verify`, idem com `cd`, `cd .swarm/harness && python3 -m auto approve` ⇒ 2 |
| CA-01 | test_ca01_controle_build_e_caminho_direto | R | `bash scripts/build.sh`, `.swarm/bin/cs-state board` ⇒ 0 |
| CA-01 | test_ca01_controle_caminho_direto_ato_humano_continua_barrado | R | caminho direto waive-verify/accept ⇒ 2 |
| CA-02 | test_ca02_subagente_ln_e_cp_l_de_protegido_recusado | D | sub `ln [-f]`/`cp -l .claude/settings.json <allowed>` ⇒ 2 |
| CA-02 | test_ca02_escrita_por_hardlink_preexistente_recusada | D | allowed vira hardlink (os.link) de settings.json: Write, Edit, `echo x >` ⇒ 2; settings intacto |
| CA-02 | test_ca02_controle_escrita_normal_no_allowed | R | Write/Edit/`echo x >` no allowed comum ⇒ 0 |
| CA-03 | test_ca03_principal_write_edit_em_registro_humano_recusado | D | Write/Edit nos 5 registros humanos ⇒ 2 |
| CA-03 | test_ca03_principal_redirect_em_registro_humano_recusado | D | `echo >> approvals.jsonl`, `echo > acceptance.json5`, `cp a team-approvals.jsonl` ⇒ 2 |
| CA-03 | test_ca03_controle_escrita_legitima_do_principal_em_swarm | R | Write `.swarm/knowledge/notas-da-ana.md`, `cs-state board` ⇒ 0 |
| CA-04 | test_ca04_principal/subagente_escritor_com_flag_de_saida_em_protegido | D | git diff/show/log --output, curl -o, wget -O, tar -C, unzip -d em protegido ⇒ 2 |
| CA-04 | test_ca04_controle_leitura_git_e_destino_permitido | R | git diff, git log -1, sub `curl -o <allowed>` ⇒ 0 |
| CA-05 | test_ca05_inline_e_stdin_fail_closed | D | -Sc, -Ic, -uc, `| python3 -`, `| sh -`, /dev/stdin, ruby -ne, node -pe (ambos) ⇒ 2 |
| CA-05 | test_ca05_controle_script_de_arquivo_do_projeto / _python_c_continua_barrado | R | `python3 tools/x.py` ⇒ 0; `python3 -c` ⇒ 2 |
| CA-06 | test_ca06_principal_git_que_desliga_hook_ou_reescreve_remoto | D | 13 formas (hooksPath, refspec, -f, --mirror, --delete, --no-verify/-n, branch -D, remote set-url, reflog expire) ⇒ 2 |
| CA-06 | test_ca06_subagente_git_config_remote_branch_reflog | D | sub: config hooksPath, remote set-url, branch -D, reflog expire ⇒ 2 |
| CA-06 | test_ca06_controle_leituras_git | R | git status/log/diff ⇒ 0 (ambos) |
| CA-07 | test_ca07_version_e_catalogo_0122_com_harness | D | VERSION ≥ 0.12.2; uma entrada `to: "0.12.2"` com ação harness |
| CA-07 | test_ca07_upgrade_de_alvo_0121_lista_0122_e_fecha_porta | D | alvo 0.12.1 (git archive da30e17): plano lista 0.12.2, apply reinstala guard, sub `bash <bin> waive-verify` ⇒ 2, escrita no allowed ⇒ 0 |
| CA-07 | test_ca07_alvo_0121_porta_aberta_antes_controle | R | na 0.12.1 a porta está aberta (fixture reproduz o defeito) |

Fora deste oráculo (o portão mede): oráculos iter16..iter22 verdes; suítes; `def` removido; `dotnet -o` (sem dotnet
na fixture); que o motor/comandos humanos continuam gravando os registros (CA-03, 2ª metade).
Medir: `python3 medir.py` (e `/usr/bin/python3 medir.py`). Base em base.txt.
