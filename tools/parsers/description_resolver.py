"""Shared SmartFormat template resolver for card/relic/potion descriptions."""
import re


def _lookup(name: str, vars_dict: dict[str, int | str], default=None):
    """Case-insensitive variable lookup."""
    if name in vars_dict:
        return vars_dict[name]
    for k, v in vars_dict.items():
        if k.lower() == name.lower():
            return v
    return default


def resolve_description(raw: str, vars_dict: dict[str, int | str], is_upgraded: bool = False) -> str:
    """Resolve SmartFormat templates in descriptions."""
    text = raw

    # Handle {IfUpgraded:show:A|B} or {IfUpgraded:show:A}
    def resolve_if_upgraded(m):
        parts = m.group(1)
        if "|" in parts:
            a, b = parts.split("|", 1)
            return a if is_upgraded else b
        return parts if is_upgraded else ""
    text = re.sub(r'\{IfUpgraded:show:([^}]*)\}', resolve_if_upgraded, text)

    # Handle {Var:energyIcons()} and {Var:energyIcons(N)} -> [energy:N]
    def resolve_energy_icons(m):
        var_name = m.group(1)
        explicit_count = m.group(2)
        if explicit_count:
            return f"[energy:{explicit_count}]"
        val = vars_dict.get(var_name, 1)
        return f"[energy:{val}]"
    text = re.sub(r'\{(\w+):energyIcons\((\d*)\)\}', resolve_energy_icons, text)

    # Handle {Var:starIcons()} -> [star:N]
    def resolve_star_icons(m):
        var_name = m.group(1)
        val = vars_dict.get(var_name, 1)
        return f"[star:{val}]"
    text = re.sub(r'\{(\w+):starIcons\(\)\}', resolve_star_icons, text)

    # Handle {SingleStarIcon} -> [star:1]
    text = re.sub(r'\{SingleStarIcon\}', '[star:1]', text, flags=re.IGNORECASE)

    # Handle {Var:plural:singular|plural} — {} in the form is replaced with the value
    # Must handle {} inside plural forms, so we manually parse these
    def resolve_all_plurals(text):
        while True:
            m = re.search(r'\{(\w+):plural:', text)
            if not m:
                break
            start = m.start()
            var_name = m.group(1)
            rest_start = m.end()  # position after ":plural:"
            # Find the matching closing } by counting braces
            depth = 1
            i = rest_start
            while i < len(text) and depth > 0:
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                i += 1
            if depth != 0:
                break
            inner = text[rest_start:i - 1]  # content between :plural: and closing }
            pipe = inner.index("|") if "|" in inner else len(inner)
            singular = inner[:pipe]
            plural_form = inner[pipe + 1:] if pipe < len(inner) else ""
            val = _lookup(var_name, vars_dict, 2)
            result = singular if val == 1 else plural_form
            result = result.replace("{}", str(val))
            text = text[:start] + result + text[i:]
        return text
    text = resolve_all_plurals(text)

    # Handle {Var:diff()} -> value
    def resolve_diff(m):
        val = _lookup(m.group(1), vars_dict)
        return str(val) if val is not None else "X"
    text = re.sub(r'\{(\w+):diff\(\)\}', resolve_diff, text)

    # Handle remaining {Var} without formatter
    def _make_readable(name: str) -> str:
        readable = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
        readable = re.sub(r'\d+', '', readable).strip()
        return readable

    def resolve_bare(m):
        val = _lookup(m.group(1), vars_dict)
        if val is not None:
            return str(val)
        return f"[{_make_readable(m.group(1))}]"
    text = re.sub(r'\{(\w+)\}', resolve_bare, text)

    # Handle {Var:cond:...} and other complex formatters -> just show value
    def resolve_remaining(m):
        var_name = m.group(1).split(":")[0]
        val = _lookup(var_name, vars_dict)
        if val is not None:
            return str(val)
        return f"[{_make_readable(var_name)}]"
    text = re.sub(r'\{([^}]+)\}', resolve_remaining, text)

    return text


def extract_vars_from_source(content: str) -> dict[str, int]:
    """Extract DynamicVar values from C# source code."""
    all_vars: dict[str, int] = {}

    # Pattern: new XxxVar("Name", Nm, ...) — named typed vars (events use this heavily)
    # e.g. new DamageVar("RipHpLoss", 5m, ValueProp.Unblockable)
    for m in re.finditer(r'new\s+\w+Var\(\s*"(\w+)"\s*,\s*(\d+)m?(?:\s*,\s*[^)]+)?\)', content):
        all_vars[m.group(1)] = int(m.group(2))

    # Pattern: new IntVar("Name", Nm) — named int vars
    # e.g. new IntVar("RewardCount", 1m)
    for m in re.finditer(r'new\s+IntVar\(\s*"(\w+)"\s*,\s*(\d+)m?\)', content):
        all_vars[m.group(1)] = int(m.group(2))

    # Pattern: new XxxVar(Nm) or new XxxVar(N) — unnamed typed vars (cards use this)
    # Captures the type name (before "Var") and the numeric value
    for m in re.finditer(r'new\s+(\w+)Var\((\d+)m?(?:\s*,\s*[^)]+)?\)', content):
        var_type = m.group(1)  # e.g. "Damage", "Block", "Energy", "Cards", "MaxHp", "Power", "Heal"
        var_val = int(m.group(2))
        if var_type not in all_vars:
            all_vars[var_type] = var_val

    # Pattern: new PowerVar<XxxPower>(Nm) — power vars with generic type
    for m in re.finditer(r'new\s+PowerVar<(\w+?)(?:Power)?>\((\d+)m?\)', content):
        power_name = m.group(1)
        # Strip trailing "Power" if present in the name
        if power_name.endswith("Power"):
            power_name = power_name[:-5]
        power_val = int(m.group(2))
        # Store as both "XxxPower" and "Xxx" for template matching
        all_vars[f"{power_name}Power"] = power_val
        all_vars[power_name] = power_val

    # Pattern: new DynamicVar("Name", Nm) — named dynamic vars
    for m in re.finditer(r'new\s+DynamicVar\(\s*"(\w+)"\s*,\s*(\d+)m?\)', content):
        name = m.group(1)
        val = int(m.group(2))
        all_vars[name] = val

    # Pattern: new EnergyVar("Name", N) — named energy vars
    for m in re.finditer(r'new\s+EnergyVar\(\s*"(\w+)"\s*,\s*(\d+)\)', content):
        name = m.group(1)
        val = int(m.group(2))
        all_vars[name] = val

    # Pattern: new IntVar(N)
    for m in re.finditer(r'(\w+)\s*=\s*new\s+IntVar\((\d+)\)', content):
        all_vars[m.group(1)] = int(m.group(2))

    # Const values: private const int _varName = N;
    for m in re.finditer(r'private\s+const\s+int\s+_?(\w+)\s*=\s*(\d+)', content):
        name = m.group(1)
        if name not in all_vars:
            all_vars[name] = int(m.group(2))

    return all_vars
