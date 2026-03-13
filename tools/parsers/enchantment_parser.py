"""Parse enchantment data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path
from description_resolver import resolve_description, extract_vars_from_source
from path_utils import DECOMPILED, IMAGES_ROOT, LOCALIZATION_EN, LOCALIZATION_ZH, OUTPUT

ENCHANTMENTS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Enchantments"
STATIC_IMAGES = IMAGES_ROOT / "enchantments"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "enchantments.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_card_type_restriction(content: str) -> str | None:
    """Extract which card types this enchantment can be applied to."""
    m = re.search(r'CanEnchantCardType\(CardType\s+\w+\)\s*\{[^}]*cardType\s*==\s*CardType\.(\w+)', content, re.DOTALL)
    if m:
        return m.group(1)
    return None


def parse_single_enchantment(filepath: Path, localization: dict, localization_zh: dict) -> dict | None:
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    if class_name.startswith("Deprecated") or class_name.startswith("Mock"):
        return None

    ench_id = class_name_to_id(class_name)

    # Extract variable values from source
    all_vars = extract_vars_from_source(content)

    # Extract Amount if referenced
    amount_match = re.search(r'base\.Amount', content)
    if amount_match and "Amount" not in all_vars:
        # Try to find amount from DynamicVar declarations or default
        for m in re.finditer(r'new\s+DynamicVar\("(\w+)",\s*(\d+)m?\)', content):
            all_vars[m.group(1)] = int(m.group(2))

    # Localization
    title = localization.get(f"{ench_id}.title", class_name)
    description_raw = localization.get(f"{ench_id}.description", "")
    extra_card_text_raw = localization.get(f"{ench_id}.extraCardText", "")
    title_zh = localization_zh.get(f"{ench_id}.title", title)
    description_raw_zh = localization_zh.get(f"{ench_id}.description", description_raw)
    extra_card_text_raw_zh = localization_zh.get(f"{ench_id}.extraCardText", extra_card_text_raw)

    # Resolve description templates
    description_resolved = resolve_description(description_raw, all_vars)
    desc_clean = description_resolved
    description_resolved_zh = resolve_description(description_raw_zh, all_vars)
    desc_clean_zh = description_resolved_zh

    extra_text_resolved = resolve_description(extra_card_text_raw, all_vars) if extra_card_text_raw else None
    extra_text_resolved_zh = resolve_description(extra_card_text_raw_zh, all_vars) if extra_card_text_raw_zh else None

    # Card type restriction
    card_type = parse_card_type_restriction(content)

    # Boolean properties
    is_stackable = "IsStackable => true" in content
    show_amount = "ShowAmount => true" in content

    # Image URL
    image_file = STATIC_IMAGES / f"{ench_id.lower()}.png"
    image_url = f"/images/enchantments/{ench_id.lower()}.png" if image_file.exists() else None

    return {
        "id": ench_id,
        "name": title,
        "name_zh": title_zh if title_zh != title else None,
        "description": desc_clean,
        "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        "description_raw": description_raw if description_raw != desc_clean else None,
        "description_raw_zh": description_raw_zh if description_raw_zh != description_raw else None,
        "extra_card_text": extra_text_resolved,
        "extra_card_text_zh": extra_text_resolved_zh if extra_text_resolved_zh != extra_text_resolved else None,
        "card_type": card_type,
        "is_stackable": is_stackable,
        "image_url": image_url,
    }


def parse_all_enchantments() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    enchantments = []
    for filepath in sorted(ENCHANTMENTS_DIR.glob("*.cs")):
        ench = parse_single_enchantment(filepath, localization, localization_zh)
        if ench:
            enchantments.append(ench)
    return enchantments


def main():
    OUTPUT.mkdir(exist_ok=True)
    enchantments = parse_all_enchantments()
    with open(OUTPUT / "enchantments.json", "w", encoding="utf-8") as f:
        json.dump(enchantments, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(enchantments)} enchantments -> data/enchantments.json")


if __name__ == "__main__":
    main()
