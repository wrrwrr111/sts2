"""Parse potion data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path
from description_resolver import resolve_description, extract_vars_from_source

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
POTIONS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Potions"
STATIC_IMAGES = BASE / "public" / "images" / "potions"
OUTPUT = BASE / "data"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "potions.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_single_potion(filepath: Path, localization: dict, localization_zh: dict) -> dict | None:
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    if class_name.startswith("Deprecated") or class_name.startswith("Mock"):
        return None

    potion_id = class_name_to_id(class_name)

    # Rarity
    rarity_match = re.search(r'Rarity\s*=>\s*PotionRarity\.(\w+)', content)
    rarity = rarity_match.group(1) if rarity_match else "Common"

    # Extract variable values from source
    all_vars = extract_vars_from_source(content)

    # Localization
    title = localization.get(f"{potion_id}.title", class_name)
    description_raw = localization.get(f"{potion_id}.description", "")
    title_zh = localization_zh.get(f"{potion_id}.title", title)
    description_raw_zh = localization_zh.get(f"{potion_id}.description", description_raw)

    # Resolve templates, keep [gold] for frontend rendering
    description_resolved = resolve_description(description_raw, all_vars)
    desc_clean = description_resolved
    description_resolved_zh = resolve_description(description_raw_zh, all_vars)
    desc_clean_zh = description_resolved_zh

    # Image URL
    image_file = STATIC_IMAGES / f"{potion_id.lower()}.png"
    image_url = f"/images/potions/{potion_id.lower()}.png" if image_file.exists() else None

    return {
        "id": potion_id,
        "name": title,
        "name_zh": title_zh if title_zh != title else None,
        "description": desc_clean,
        "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        "description_raw": description_raw,
        "description_raw_zh": description_raw_zh if description_raw_zh != description_raw else None,
        "rarity": rarity,
        "image_url": image_url,
    }


def parse_all_potions() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    potions = []
    for filepath in sorted(POTIONS_DIR.glob("*.cs")):
        potion = parse_single_potion(filepath, localization, localization_zh)
        if potion:
            potions.append(potion)
    return potions


def main():
    OUTPUT.mkdir(exist_ok=True)
    potions = parse_all_potions()
    with open(OUTPUT / "potions.json", "w", encoding="utf-8") as f:
        json.dump(potions, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(potions)} potions -> data/potions.json")


if __name__ == "__main__":
    main()
