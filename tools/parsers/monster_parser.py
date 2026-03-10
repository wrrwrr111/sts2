"""Parse monster data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
MONSTERS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Monsters"
ENCOUNTERS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Encounters"
IMAGES_DIR = BASE / "public" / "images" / "monsters"
OUTPUT = BASE / "data"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "monsters.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_encounter_types() -> dict[str, str]:
    """Parse encounter files to map monster class names to types (Boss/Elite/Normal)."""
    monster_types: dict[str, str] = {}
    for f in sorted(ENCOUNTERS_DIR.glob("*.cs")):
        if f.stem.startswith("Mock") or f.stem.startswith("Deprecated"):
            continue
        content = f.read_text(encoding="utf-8")
        room_match = re.search(r'RoomType\s*=>\s*RoomType\.(\w+)', content)
        if not room_match:
            continue
        room_type = room_match.group(1)
        if room_type == "Boss":
            mtype = "Boss"
        elif room_type == "Elite":
            mtype = "Elite"
        else:
            mtype = "Normal"
        for m in re.finditer(r'ModelDb\.Monster<(\w+)>', content):
            monster_name = m.group(1)
            # Boss/Elite takes priority over Normal
            if monster_name not in monster_types or mtype in ("Boss", "Elite"):
                if monster_name in monster_types and monster_types[monster_name] == "Boss" and mtype == "Elite":
                    continue  # Don't downgrade Boss to Elite
                monster_types[monster_name] = mtype
    return monster_types


def parse_single_monster(filepath: Path, localization: dict, localization_zh: dict, encounter_types: dict) -> dict | None:
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    # Skip test/mock/deprecated monsters
    skip_prefixes = ("Mock", "Deprecated")
    skip_names = {
        "BigDummy", "FakeMerchantMonster", "MultiAttackMoveMonster",
        "OneHpMonster", "SingleAttackMoveMonster", "TenHpMonster",
    }
    if class_name.startswith(skip_prefixes) or class_name in skip_names:
        return None

    monster_id = class_name_to_id(class_name)

    # HP - try various patterns
    min_hp = None
    max_hp = None

    # Pattern: override int MinInitialHp => AscensionHelper.GetValueIfAscension(level, asc_val, normal_val)
    min_hp_asc = re.search(r'MinInitialHp\s*=>\s*AscensionHelper\.GetValueIfAscension\(\w+\.(\w+),\s*(\d+),\s*(\d+)\)', content)
    max_hp_asc = re.search(r'MaxInitialHp\s*=>\s*AscensionHelper\.GetValueIfAscension\(\w+\.(\w+),\s*(\d+),\s*(\d+)\)', content)

    if min_hp_asc:
        min_hp = int(min_hp_asc.group(3))  # Normal value
        min_hp_asc_val = int(min_hp_asc.group(2))  # Ascension value
    else:
        min_hp_simple = re.search(r'MinInitialHp\s*=>\s*(\d+)', content)
        if min_hp_simple:
            min_hp = int(min_hp_simple.group(1))
        min_hp_asc_val = None

    if max_hp_asc:
        max_hp = int(max_hp_asc.group(3))
        max_hp_asc_val = int(max_hp_asc.group(2))
    else:
        max_hp_simple = re.search(r'MaxInitialHp\s*=>\s*(\d+)', content)
        if max_hp_simple:
            max_hp = int(max_hp_simple.group(1))
        max_hp_asc_val = None

    # Moves - extract from MoveState definitions
    moves = []
    # Pattern: new MoveState("NAME", method, new IntentType(args))
    for m in re.finditer(r'new MoveState\(\s*"(\w+)"', content):
        move_name = m.group(1)
        moves.append(move_name)

    # Damage values from move methods
    damage_values = {}
    # Pattern: GetValueIfAscension(level, asc_val, normal_val) for damage
    for dm in re.finditer(r'(\w+)Damage\s*=>\s*AscensionHelper\.GetValueIfAscension\(\w+\.\w+,\s*(\d+),\s*(\d+)\)', content):
        damage_values[dm.group(1)] = {"normal": int(dm.group(3)), "ascension": int(dm.group(2))}
    # Simple damage: private int XDamage => N;
    for dm in re.finditer(r'(\w+)Damage\s*=>\s*(\d+)\s*;', content):
        if dm.group(1) not in damage_values:
            damage_values[dm.group(1)] = {"normal": int(dm.group(2))}
    # Const damage: private const int _xDamage = N;
    for dm in re.finditer(r'private\s+const\s+int\s+_(\w*)[Dd]amage\s*=\s*(\d+)', content):
        name = dm.group(1) or "base"
        if name not in damage_values:
            damage_values[name] = {"normal": int(dm.group(2))}

    # Block values
    block_values = {}
    for bm in re.finditer(r'(\w+)Block\s*=>\s*(\d+)', content):
        block_values[bm.group(1)] = int(bm.group(2))
    for bm in re.finditer(r'private\s+const\s+int\s+_(\w*)[Bb]lock\s*=\s*(\d+)', content):
        name = bm.group(1) or "base"
        block_values[name] = int(bm.group(2))

    # Monster type from encounter data
    monster_type = encounter_types.get(class_name, "Normal")

    # Localization - get name and move names
    name = localization.get(f"{monster_id}.name", class_name)
    name_zh = localization_zh.get(f"{monster_id}.name", name)
    move_details = []
    for move in moves:
        # Localization keys omit the _MOVE suffix (e.g. "INCANTATION" not "INCANTATION_MOVE")
        loc_move = re.sub(r'_MOVE$', '', move)
        loc_key = f"{monster_id}.moves.{loc_move}.title"
        move_title = localization.get(loc_key, loc_move.replace("_", " ").title())
        move_title_zh = localization_zh.get(loc_key, move_title)
        move_details.append({
            "id": loc_move,
            "name": move_title,
            "name_zh": move_title_zh if move_title_zh != move_title else None,
        })

    # Skip monsters with no meaningful data (segments, stubs)
    if not min_hp and not move_details and not damage_values:
        return None

    # Image URL - check if a matching image exists
    # Some monsters share sprites or have different filenames than their IDs
    IMAGE_ALIASES = {
        "CALCIFIED_CULTIST": "calcified_cultist",
        "DAMP_CULTIST": "damp_cultist",
        "GLOBE_HEAD": "orb_head",
        "TORCH_HEAD_AMALGAM": "amalgam",
        "SKULKING_COLONY": "skulkling_colomy",
        "LIVING_FOG": "living_smog",
        "THE_ADVERSARY_MK_ONE": "the_adversary_placeholder",
        "THE_ADVERSARY_MK_TWO": "the_adversary_placeholder",
        "THE_ADVERSARY_MK_THREE": "the_adversary_placeholder",
        "BOWLBUG_EGG": "bowlbug_egg",
        "BOWLBUG_NECTAR": "bowlbug_nectar",
        "BOWLBUG_ROCK": "bowlbug_rock",
        "BOWLBUG_SILK": "bowlbug_silk",
    }
    img_name = IMAGE_ALIASES.get(monster_id, monster_id.lower())
    image_file = IMAGES_DIR / f"{img_name}.png"
    image_url = f"/images/monsters/{img_name}.png" if image_file.exists() else None

    return {
        "id": monster_id,
        "name": name,
        "name_zh": name_zh if name_zh != name else None,
        "type": monster_type,
        "min_hp": min_hp,
        "max_hp": max_hp,
        "min_hp_ascension": min_hp_asc_val if min_hp_asc else None,
        "max_hp_ascension": max_hp_asc_val if max_hp_asc else None,
        "moves": move_details if move_details else None,
        "damage_values": damage_values if damage_values else None,
        "block_values": block_values if block_values else None,
        "image_url": image_url,
    }


def parse_all_monsters() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    encounter_types = parse_encounter_types()
    monsters = []
    for filepath in sorted(MONSTERS_DIR.glob("*.cs")):
        monster = parse_single_monster(filepath, localization, localization_zh, encounter_types)
        if monster:
            monsters.append(monster)
    return monsters


def main():
    OUTPUT.mkdir(exist_ok=True)
    monsters = parse_all_monsters()
    with open(OUTPUT / "monsters.json", "w", encoding="utf-8") as f:
        json.dump(monsters, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(monsters)} monsters -> data/monsters.json")


if __name__ == "__main__":
    main()
