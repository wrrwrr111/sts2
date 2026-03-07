"""Parse card data from decompiled C# files and localization JSON."""
import json
import os
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
CARDS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Cards"
POOLS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.CardPools"
STATIC_IMAGES = BASE / "public" / "images" / "cards"
OUTPUT = BASE / "data"

CARD_TYPE_MAP = {0: "None", 1: "Attack", 2: "Skill", 3: "Power", 4: "Status", 5: "Curse", 6: "Quest"}
CARD_RARITY_MAP = {0: "None", 1: "Basic", 2: "Common", 3: "Uncommon", 4: "Rare", 5: "Ancient", 6: "Event", 7: "Token", 8: "Status", 9: "Curse", 10: "Quest"}
TARGET_TYPE_MAP = {0: "None", 1: "Self", 2: "AnyEnemy", 3: "AllEnemies", 4: "RandomEnemy", 5: "AnyPlayer", 6: "AnyAlly", 7: "AllAllies", 8: "TargetedNoCreature", 9: "Osty"}

# Map enum names to values for when code uses named enums
CARD_TYPE_NAME = {"Attack": "Attack", "Skill": "Skill", "Power": "Power", "Status": "Status", "Curse": "Curse", "Quest": "Quest", "None": "None"}
CARD_RARITY_NAME = {"Basic": "Basic", "Common": "Common", "Uncommon": "Uncommon", "Rare": "Rare", "Ancient": "Ancient", "Event": "Event", "Token": "Token", "Status": "Status", "Curse": "Curse", "Quest": "Quest", "None": "None"}
TARGET_TYPE_NAME = {"None": "None", "Self": "Self", "AnyEnemy": "AnyEnemy", "AllEnemies": "AllEnemies", "RandomEnemy": "RandomEnemy", "AnyPlayer": "AnyPlayer", "AnyAlly": "AnyAlly", "AllAllies": "AllAllies", "TargetedNoCreature": "TargetedNoCreature", "Osty": "Osty"}


def class_name_to_id(name: str) -> str:
    """Convert PascalCase class name to SNAKE_CASE id."""
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "cards.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_card_pools() -> dict[str, str]:
    """Parse card pool files to map card class names to character colors."""
    card_to_color = {}
    pool_map = {
        "IroncladCardPool.cs": "ironclad",
        "SilentCardPool.cs": "silent",
        "DefectCardPool.cs": "defect",
        "NecrobinderCardPool.cs": "necrobinder",
        "RegentCardPool.cs": "regent",
        "ColorlessCardPool.cs": "colorless",
        "CurseCardPool.cs": "curse",
        "StatusCardPool.cs": "status",
        "EventCardPool.cs": "event",
        "TokenCardPool.cs": "token",
        "QuestCardPool.cs": "quest",
    }
    for filename, color in pool_map.items():
        filepath = POOLS_DIR / filename
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8")
        for match in re.finditer(r'ModelDb\.Card<(\w+)>\(\)', content):
            card_to_color[match.group(1)] = color
    return card_to_color


def parse_single_card(filepath: Path, localization: dict, localization_zh: dict, card_pools: dict) -> dict | None:
    """Parse a single card C# file."""
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    # Extract constructor: base(cost, CardType.X, CardRarity.Y, TargetType.Z)
    base_match = re.search(
        r':\s*base\(\s*(-?\d+)\s*,\s*CardType\.(\w+)\s*,\s*CardRarity\.(\w+)\s*,\s*TargetType\.(\w+)',
        content
    )
    if not base_match:
        # Some cards use numeric enum values
        base_match = re.search(r':\s*base\(\s*(-?\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', content)
        if base_match:
            cost = int(base_match.group(1))
            card_type = CARD_TYPE_MAP.get(int(base_match.group(2)), "Unknown")
            rarity = CARD_RARITY_MAP.get(int(base_match.group(3)), "Unknown")
            target = TARGET_TYPE_MAP.get(int(base_match.group(4)), "Unknown")
        else:
            return None
    else:
        cost = int(base_match.group(1))
        card_type = CARD_TYPE_NAME.get(base_match.group(2), base_match.group(2))
        rarity = CARD_RARITY_NAME.get(base_match.group(3), base_match.group(3))
        target = TARGET_TYPE_NAME.get(base_match.group(4), base_match.group(4))

    card_id = class_name_to_id(class_name)

    # Extract dynamic vars
    damage = None
    block = None
    magic_number = None
    keywords = []
    # Collect ALL var values into a dict for description rendering
    all_vars: dict[str, int] = {}

    # DamageVar patterns
    dmg_match = re.search(r'new DamageVar\((\d+)m', content)
    if dmg_match:
        damage = int(dmg_match.group(1))
        all_vars["Damage"] = damage

    # BlockVar patterns
    blk_match = re.search(r'new BlockVar\((\d+)m', content)
    if blk_match:
        block = int(blk_match.group(1))
        all_vars["Block"] = block

    # PowerVar patterns - collect all
    powers_applied = []
    for pm in re.finditer(r'new PowerVar<(\w+)>\((\d+)m\)', content):
        power_name = pm.group(1)
        power_val = int(pm.group(2))
        powers_applied.append({"power": power_name.replace("Power", ""), "amount": power_val})
        all_vars[power_name] = power_val

    # Generic Var patterns: new XxxVar(Nm) or new XxxVar(N)
    for vm in re.finditer(r'new (\w+)Var(?:<\w+>)?\((\d+)m?\)', content):
        var_type = vm.group(1)
        var_val = int(vm.group(2))
        # Map var type to template name
        var_map = {
            "Cards": "Cards", "Energy": "Energy", "HpLoss": "HpLoss",
            "ExtraDamage": "ExtraDamage", "Repeat": "Repeat", "Summon": "Summon",
            "Forge": "Forge", "Gold": "Gold", "Heal": "Heal", "MaxHp": "MaxHp",
            "Stars": "Stars", "OstyDamage": "OstyDamage", "Int": "Int",
            "CalculatedDamage": "CalculatedDamage", "CalculatedBlock": "CalculatedBlock",
            "CalculationBase": "CalculationBase", "CalculationExtra": "CalculationExtra",
            "Calculated": "Calculated",
        }
        name = var_map.get(var_type, var_type)
        if name not in all_vars:
            all_vars[name] = var_val

    # Also capture named DynamicVar instances: Xxx = new DynamicVar("Xxx", N)
    for dv in re.finditer(r'new DynamicVar\("(\w+)",\s*(\d+)m?\)', content):
        all_vars[dv.group(1)] = int(dv.group(2))
    # DynamicVar with just a number: new DynamicVar(N)
    for dv in re.finditer(r'(\w+)\s*=\s*new DynamicVar\((\d+)m?\)', content):
        all_vars[dv.group(1)] = int(dv.group(2))

    # IntVar: Xxx = new IntVar(N)
    for iv in re.finditer(r'(\w+)\s*=\s*new IntVar\((\d+)\)', content):
        all_vars[iv.group(1)] = int(iv.group(2))

    # Star cost: CanonicalStarCost => N means the card costs stars
    star_cost_match = re.search(r'CanonicalStarCost\s*=>\s*(\d+)', content)
    if star_cost_match:
        all_vars["StarCost"] = int(star_cost_match.group(1))

    cards_draw = all_vars.get("Cards")
    energy_gain = all_vars.get("Energy")
    hp_loss = all_vars.get("HpLoss")

    # X-cost detection
    is_x_cost = bool(re.search(r'HasEnergyCostX\s*=>\s*true', content) or re.search(r'CostsX', content))
    is_x_star_cost = bool(re.search(r'HasStarCostX\s*=>\s*true', content))

    # Upgrade info
    upgrade_damage = None
    upgrade_block = None
    dmg_up = re.search(r'Damage\.UpgradeValueBy\((\d+)m\)', content)
    if dmg_up:
        upgrade_damage = int(dmg_up.group(1))
    blk_up = re.search(r'Block\.UpgradeValueBy\((\d+)m\)', content)
    if blk_up:
        upgrade_block = int(blk_up.group(1))

    # Cost upgrade
    cost_upgrade = None
    cost_up = re.search(r'UpgradeEnergyCost\((-?\d+)\)', content)
    if cost_up:
        cost_upgrade = int(cost_up.group(1))
    else:
        cost_delta = re.search(r'EnergyCost\.UpgradeBy\((-?\d+)\)', content)
        if cost_delta and cost is not None and not is_x_cost:
            cost_upgrade = cost + int(cost_delta.group(1))

    # Keywords from CanonicalKeywords array (most common pattern)
    canonical_kw_match = re.search(r'CanonicalKeywords\s*=>', content)
    canonical_keywords_block = ""
    if canonical_kw_match:
        # Extract the block after CanonicalKeywords =>
        start = canonical_kw_match.end()
        # Find the matching closing of the property (next semicolon at property level)
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            elif content[i] == ';' and depth <= 0:
                end = i
                break
        canonical_keywords_block = content[start:end]

    for kw in ("Exhaust", "Innate", "Ethereal", "Retain", "Unplayable", "Sly", "Eternal"):
        if f"CardKeyword.{kw}" in canonical_keywords_block:
            keywords.append(kw)

    # Keywords from property overrides (additional patterns)
    if "Ethereal" not in keywords and re.search(r'IsEthereal\s*=>\s*true', content):
        keywords.append("Ethereal")
    if "Innate" not in keywords and re.search(r'IsInnate\s*=>\s*true', content):
        keywords.append("Innate")
    if "Exhaust" not in keywords:
        if re.search(r'ExhaustOnPlay\s*=>\s*true', content) or re.search(r'ShouldExhaust\s*=>\s*true', content):
            keywords.append("Exhaust")
        if re.search(r'CardKeyword\.Exhaust', content) and 'AddKeyword' in content:
            keywords.append("Exhaust")
    if "Retain" not in keywords and (re.search(r'IsRetain\s*=>\s*true', content) or re.search(r'IsRetainable\s*=>\s*true', content)):
        keywords.append("Retain")
    if "Unplayable" not in keywords and re.search(r'IsUnplayable\s*=>\s*true', content):
        keywords.append("Unplayable")
    if "Sly" not in keywords and re.search(r'CardKeyword\.Sly', content) and 'AddKeyword' in content:
        keywords.append("Sly")
    if "Eternal" not in keywords and re.search(r'CardKeyword\.Eternal', content) and 'AddKeyword' in content:
        keywords.append("Eternal")

    # Tags (Strike, Defend, Minion, OstyAttack, Shiv)
    tags = []
    for tag in ("Strike", "Defend", "Minion", "OstyAttack", "Shiv"):
        if re.search(rf'CardTag\.{tag}', content):
            tags.append(tag)

    # Multi-hit
    hit_count = None
    hit_match = re.search(r'WithHitCount\((\d+)\)', content)
    if hit_match:
        hit_count = int(hit_match.group(1))

    # Get localization
    title = localization.get(f"{card_id}.title", class_name)
    description = localization.get(f"{card_id}.description", "")
    title_zh = localization_zh.get(f"{card_id}.title", title)
    description_zh = localization_zh.get(f"{card_id}.description", description)

    # Note: description will be rendered with resolve_description below

    # Character color from pool
    color = card_pools.get(class_name, "unknown")

    # Render description by resolving template vars
    def resolve_description(raw: str, vars_dict: dict[str, int], is_upgraded: bool = False) -> str:
        """Resolve SmartFormat templates in card descriptions."""
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

        # Handle {Var:plural:singular|plural}
        def resolve_plural(m):
            var_name = m.group(1)
            singular = m.group(2)
            plural_form = m.group(3)
            val = vars_dict.get(var_name, 2)
            return singular if val == 1 else plural_form
        text = re.sub(r'\{(\w+):plural:([^|]+)\|([^}]+)\}', resolve_plural, text)

        # Handle {Var:diff()} -> value
        def resolve_diff(m):
            var_name = m.group(1)
            val = vars_dict.get(var_name)
            if val is None:
                # Try case-insensitive lookup
                for k, v in vars_dict.items():
                    if k.lower() == var_name.lower():
                        return str(v)
                return "X"
            return str(val)
        text = re.sub(r'\{(\w+):diff\(\)\}', resolve_diff, text)

        # Handle remaining {Var} without formatter
        def resolve_bare(m):
            var_name = m.group(1)
            val = vars_dict.get(var_name)
            if val is None:
                for k, v in vars_dict.items():
                    if k.lower() == var_name.lower():
                        return str(v)
            return str(val) if val is not None else ""
        text = re.sub(r'\{(\w+)\}', resolve_bare, text)

        # Handle {Var:cond:...} and other complex formatters we can't resolve -> just show value
        def resolve_remaining(m):
            inner = m.group(1)
            var_name = inner.split(":")[0]
            val = vars_dict.get(var_name)
            if val is None:
                for k, v in vars_dict.items():
                    if k.lower() == var_name.lower():
                        return str(v)
            return str(val) if val is not None else ""
        text = re.sub(r'\{([^}]+)\}', resolve_remaining, text)

        return text

    desc_rendered = resolve_description(description, all_vars)
    desc_rendered_zh = resolve_description(description_zh, all_vars)

    def apply_upgrade(vars_dict: dict[str, int], upgrade_dict: dict) -> dict[str, int]:
        """Apply upgrade deltas to a vars dict, matching keys case-insensitively."""
        upgraded = dict(vars_dict)
        if not upgrade_dict:
            return upgraded

        for key, raw_val in upgrade_dict.items():
            if key == "cost":
                continue
            if isinstance(raw_val, str) and raw_val.startswith(("+", "-")):
                try:
                    delta = int(raw_val)
                except ValueError:
                    continue
            elif isinstance(raw_val, int):
                delta = raw_val
            else:
                continue

            target_key = None
            for k in upgraded.keys():
                if k.lower() == key.lower():
                    target_key = k
                    break
            if target_key is None:
                if key.lower() == "damage":
                    target_key = "Damage"
                elif key.lower() == "block":
                    target_key = "Block"
            if target_key is None:
                continue
            try:
                upgraded[target_key] = int(upgraded.get(target_key, 0)) + delta
            except ValueError:
                continue
        return upgraded

    star_cost = all_vars.get("StarCost")

    card = {
        "id": card_id,
        "name": title,
        "name_zh": title_zh if title_zh != title else None,
        "description": desc_rendered,
        "description_zh": desc_rendered_zh if desc_rendered_zh != desc_rendered else None,
        "description_raw": description,
        "description_raw_zh": description_zh if description_zh != description else None,
        "description_upgraded": None,
        "description_upgraded_zh": None,
        "cost": cost,
        "is_x_cost": is_x_cost if is_x_cost else None,
        "is_x_star_cost": is_x_star_cost if is_x_star_cost else None,
        "star_cost": star_cost,
        "type": card_type,
        "rarity": rarity,
        "target": target,
        "color": color,
        "damage": damage,
        "block": block,
        "hit_count": hit_count,
        "powers_applied": powers_applied if powers_applied else None,
        "cards_draw": cards_draw,
        "energy_gain": energy_gain,
        "hp_loss": hp_loss,
        "keywords": keywords if keywords else None,
        "tags": tags if tags else None,
        "vars": all_vars if all_vars else None,
        "upgrade": {},
        "image_url": f"/images/cards/{card_id.lower()}.png" if (STATIC_IMAGES / f"{card_id.lower()}.png").exists() else None,
        "beta_image_url": f"/images/cards/beta/{card_id.lower()}.png" if (STATIC_IMAGES / "beta" / f"{card_id.lower()}.png").exists() else None,
    }

    if upgrade_damage:
        card["upgrade"]["damage"] = f"+{upgrade_damage}"
    if upgrade_block:
        card["upgrade"]["block"] = f"+{upgrade_block}"
    if cost_upgrade is not None:
        card["upgrade"]["cost"] = cost_upgrade

    # Upgrade power vars
    for pm in re.finditer(r'(\w+)\.UpgradeValueBy\((\d+)m\)', content):
        var_name = pm.group(1)
        val = int(pm.group(2))
        if var_name not in ("Damage", "Block"):
            card["upgrade"][var_name.lower()] = f"+{val}"

    if not card["upgrade"]:
        card["upgrade"] = None
    else:
        upgraded_vars = apply_upgrade(all_vars, card["upgrade"])
        card["description_upgraded"] = resolve_description(description, upgraded_vars, True)
        card["description_upgraded_zh"] = resolve_description(description_zh, upgraded_vars, True)

    return card


def parse_all_cards() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    card_pools = parse_card_pools()
    cards = []

    for filepath in sorted(CARDS_DIR.glob("*.cs")):
        if filepath.stem.startswith("Mock") or filepath.stem == "DeprecatedCard":
            continue
        card = parse_single_card(filepath, localization, localization_zh, card_pools)
        if card:
            cards.append(card)

    return cards


def main():
    OUTPUT.mkdir(exist_ok=True)
    cards = parse_all_cards()
    with open(OUTPUT / "cards.json", "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(cards)} cards -> data/cards.json")


if __name__ == "__main__":
    main()
