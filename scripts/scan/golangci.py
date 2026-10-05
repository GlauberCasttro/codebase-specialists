"""Leitura do .golangci.yml (v1 e v2) → linters habilitados e regras depguard (fronteiras declaradas).

Só o que o arquivo DECLARA: `linters.enable` (lista), `enable-all`/`disable-all` (v1), `default` (v2),
`linters-settings.depguard.rules` (v1) / `linters.settings.depguard.rules` (v2). Arquivo que o
yamlmini não lê → `{"error": ...}` e nenhum número é inventado.
"""

from . import yamlmini


def parse(text):
    try:
        obj, lines = yamlmini.load(text)
    except yamlmini.YamlError as exc:
        return {"error": str(exc)}
    if not isinstance(obj, dict):
        return {"error": "raiz não é um mapa"}
    linters = obj.get("linters") if isinstance(obj.get("linters"), dict) else {}
    version = str(obj.get("version") or "1")
    enable = [x for x in (linters.get("enable") or []) if isinstance(x, str)]
    disable = [x for x in (linters.get("disable") or []) if isinstance(x, str)]
    default = linters.get("default")
    if version.startswith("2"):
        base = default or "standard"
        settings_path = ("linters", "settings")
    else:
        base = "all" if linters.get("enable-all") else ("none" if linters.get("disable-all") else "standard")
        settings_path = ("linters-settings",)
    settings = yamlmini.get(obj, *settings_path) or {}
    formatters = yamlmini.get(obj, "formatters", "enable") or []
    rules = []
    dg_rules = yamlmini.get(settings, "depguard", "rules") if isinstance(settings, dict) else None
    if isinstance(dg_rules, dict):
        for name in sorted(dg_rules):
            r = dg_rules[name] if isinstance(dg_rules[name], dict) else {}
            deny = []
            for i, d in enumerate(r.get("deny") or []):
                if isinstance(d, dict) and d.get("pkg"):
                    deny.append({"pkg": str(d["pkg"]), "desc": str(d.get("desc") or ""),
                                 "line": lines.get(settings_path + ("depguard", "rules", name, "deny", i))})
                elif isinstance(d, str):
                    deny.append({"pkg": d, "desc": "", "line": None})
            allow = [str(a) for a in (r.get("allow") or []) if isinstance(a, (str, int))]
            rules.append({"name": name, "line": lines.get(settings_path + ("depguard", "rules", name)),
                          "files": [str(f) for f in (r.get("files") or []) if isinstance(f, (str, int))],
                          "deny": deny, "allow": allow, "list_mode": r.get("list-mode")})
    return {"version": version, "base": base, "enable": enable, "disable": disable,
            "enable_line": lines.get(("linters", "enable")), "formatters": [f for f in formatters
                                                                          if isinstance(f, str)],
            "depguard_enabled": "depguard" in enable or (base == "all" and "depguard" not in disable),
            "depguard_rules": rules}


def file_matches(rel, patterns, is_test):
    """Semântica de `files` do depguard v2: sem padrão positivo = todos; `!` exclui; $all, $test."""
    from cslib import paths

    def m(p):
        if p == "$all":
            return True
        if p == "$test":
            return is_test
        return paths.glob_match(rel, p) or paths.glob_match(rel, "**/" + p.lstrip("/"))

    pos = [p for p in patterns if not p.startswith("!")]
    neg = [p[1:] for p in patterns if p.startswith("!")]
    if pos and not any(m(p) for p in pos):
        return False
    return not any(m(p) for p in neg)
