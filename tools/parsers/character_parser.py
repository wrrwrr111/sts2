"""Parse character data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
CHARS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Characters"
OUTPUT = BASE / "data"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "characters.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_character(filepath: Path, localization: dict, localization_zh: dict) -> dict | None:
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    if class_name in ("RandomCharacter", "Deprived"):
        return None

    char_id = class_name_to_id(class_name)

    # Starting HP
    hp_match = re.search(r'StartingHp\s*=>\s*(\d+)', content)
    starting_hp = int(hp_match.group(1)) if hp_match else None

    # Starting Gold
    gold_match = re.search(r'StartingGold\s*=>\s*(\d+)', content)
    starting_gold = int(gold_match.group(1)) if gold_match else None

    # Starting deck
    starting_deck = []
    for m in re.finditer(r'ModelDb\.Card<(\w+)>\(\)', content):
        # Only cards in StartingDeck block
        starting_deck.append(m.group(1))

    # Starting relics
    starting_relics = []
    for m in re.finditer(r'ModelDb\.Relic<(\w+)>\(\)', content):
        starting_relics.append(m.group(1))

    # Gender
    gender_match = re.search(r'Gender\s*=>\s*CharacterGender\.(\w+)', content)
    gender = gender_match.group(1) if gender_match else None

    # Color
    color_match = re.search(r'NameColor\s*=>\s*StsColors\.(\w+)', content)
    color = color_match.group(1) if color_match else None

    # Max Energy
    energy_match = re.search(r'MaxEnergy\s*=>\s*(\d+)', content)
    max_energy = int(energy_match.group(1)) if energy_match else 3

    # Orb slots (Defect)
    orb_match = re.search(r'BaseOrbSlotCount\s*=>\s*(\d+)', content)
    orb_slots = int(orb_match.group(1)) if orb_match else None

    # Unlocks after
    unlock_match = re.search(r'UnlocksAfterRunAs\s*=>\s*ModelDb\.Character<(\w+)>', content)
    unlocks_after = unlock_match.group(1) if unlock_match else None

    # Localization
    title = localization.get(f"{char_id}.title", class_name)
    description = localization.get(f"{char_id}.description", "")
    title_zh = localization_zh.get(f"{char_id}.title", title)
    description_zh = localization_zh.get(f"{char_id}.description", description)
    desc_clean = description
    desc_clean_zh = description_zh

    return {
        "id": char_id,
        "name": title,
        "name_zh": title_zh if title_zh != title else None,
        "description": desc_clean,
        "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        "starting_hp": starting_hp,
        "starting_gold": starting_gold,
        "max_energy": max_energy,
        "orb_slots": orb_slots,
        "starting_deck": starting_deck,
        "starting_relics": starting_relics,
        "unlocks_after": unlocks_after,
        "gender": gender,
        "color": color,
        "image_url": f"/images/characters/char_select_{char_id.lower()}.png",
    }


def parse_all_characters() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    characters = []
    for filepath in sorted(CHARS_DIR.glob("*.cs")):
        char = parse_character(filepath, localization, localization_zh)
        if char:
            characters.append(char)
    return characters


def main():
    OUTPUT.mkdir(exist_ok=True)
    characters = parse_all_characters()
    with open(OUTPUT / "characters.json", "w", encoding="utf-8") as f:
        json.dump(characters, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(characters)} characters -> data/characters.json")


if __name__ == "__main__":
    main()
