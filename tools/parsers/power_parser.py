"""Parse power/buff/debuff data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path
from description_resolver import resolve_description, extract_vars_from_source
from path_utils import DECOMPILED, IMAGES_ROOT, LOCALIZATION_EN, LOCALIZATION_ZH, OUTPUT

POWERS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Powers"
POWERS_IMAGES = IMAGES_ROOT / "powers"

# Aliases for powers whose icon filename doesn't match the ID pattern
IMAGE_ALIASES: dict[str, str] = {
    "TEMPORARY_DEXTERITY": "dexterity_down_power.png",
}


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "powers.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_power_strings(power_id: str, class_name: str, localization: dict) -> tuple[str, str, str]:
    """Return (title, smart_description_raw, plain_description_raw) for a power in one locale."""
    title = localization.get(f"{power_id}.title")
    if title is None:
        title = localization.get(f"{power_id}_POWER.title")
    if title is None:
        full_id = class_name_to_id(class_name)
        title = localization.get(f"{full_id}.title", class_name)

    desc_key = power_id
    if f"{power_id}.smartDescription" not in localization and f"{power_id}.description" not in localization:
        desc_key = f"{power_id}_POWER" if f"{power_id}_POWER.smartDescription" in localization else class_name_to_id(class_name)

    smart_raw = localization.get(f"{desc_key}.smartDescription", "")
    plain_raw = localization.get(f"{desc_key}.description", "")

    return title, smart_raw, plain_raw


def parse_single_power(filepath: Path, localization: dict, localization_zh: dict) -> dict | None:
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    if class_name.startswith("Deprecated") or class_name.startswith("Mock"):
        return None

    # Strip "Power" suffix for ID if present
    base_name = class_name
    if base_name.endswith("Power"):
        base_name = base_name[:-5]
    power_id = class_name_to_id(base_name)

    # PowerType: Buff, Debuff, or None/neutral
    type_match = re.search(r'(?:override\s+)?PowerType\s+Type\s*(?:=>|=)\s*PowerType\.(\w+)', content)
    power_type = type_match.group(1) if type_match else "None"

    # StackType: Counter, Single, None
    stack_match = re.search(r'(?:override\s+)?PowerStackType\s+StackType\s*(?:=>|=)\s*PowerStackType\.(\w+)', content)
    stack_type = stack_match.group(1) if stack_match else "None"

    # AllowNegative
    allow_negative = bool(re.search(r'AllowNegative\s*(?:=>|=)\s*true', content))

    # Extract variable values from source
    all_vars = extract_vars_from_source(content)
    all_vars.setdefault("OwnerName", "this creature")

    # Localization strings in both locales
    title, smart_raw, plain_raw = get_power_strings(power_id, class_name, localization)
    title_zh, smart_raw_zh, plain_raw_zh = get_power_strings(power_id, class_name, localization_zh)

    # Prefer smartDescription but fall back to plain description for unresolved templates
    if smart_raw:
        description_raw = smart_raw
        description_resolved = resolve_description(smart_raw, all_vars)
        amount_missing = "{Amount" in smart_raw and "Amount" not in all_vars
        has_artifacts = bool(re.search(r'\[Amount\]|\[Applier|:cond:|==\d+\?|>\d+\?', description_resolved))
        if (amount_missing or has_artifacts) and plain_raw:
            description_raw = plain_raw
            description_resolved = resolve_description(plain_raw, all_vars)
    elif plain_raw:
        description_raw = plain_raw
        description_resolved = resolve_description(plain_raw, all_vars)
    else:
        description_raw = ""
        description_resolved = ""

    if smart_raw_zh:
        description_raw_zh = smart_raw_zh
        description_resolved_zh = resolve_description(smart_raw_zh, all_vars)
        amount_missing_zh = "{Amount" in smart_raw_zh and "Amount" not in all_vars
        has_artifacts_zh = bool(re.search(r'\[Amount\]|\[Applier|:cond:|==\d+\?|>\d+\?', description_resolved_zh))
        if (amount_missing_zh or has_artifacts_zh) and plain_raw_zh:
            description_raw_zh = plain_raw_zh
            description_resolved_zh = resolve_description(plain_raw_zh, all_vars)
    elif plain_raw_zh:
        description_raw_zh = plain_raw_zh
        description_resolved_zh = resolve_description(plain_raw_zh, all_vars)
    else:
        description_raw_zh = description_raw
        description_resolved_zh = description_resolved

    desc_clean = description_resolved
    desc_clean_zh = description_resolved_zh

    # Resolve image URL
    image_url = None
    if power_id in IMAGE_ALIASES:
        icon_file = POWERS_IMAGES / IMAGE_ALIASES[power_id]
    else:
        icon_file = POWERS_IMAGES / f"{power_id.lower()}_power.png"
    if icon_file.exists():
        image_url = f"/images/powers/{icon_file.name}"

    return {
        "id": power_id,
        "name": title,
        "name_zh": title_zh if title_zh != title else None,
        "description": desc_clean,
        "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        "description_raw": description_raw if description_raw != desc_clean else None,
        "description_raw_zh": description_raw_zh if description_raw_zh != description_raw else None,
        "type": power_type,
        "stack_type": stack_type,
        "allow_negative": allow_negative if allow_negative else None,
        "image_url": image_url,
    }


def parse_all_powers() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    powers = []
    for filepath in sorted(POWERS_DIR.glob("*.cs")):
        power = parse_single_power(filepath, localization, localization_zh)
        if power:
            powers.append(power)
    return powers


def main():
    OUTPUT.mkdir(exist_ok=True)
    powers = parse_all_powers()
    with open(OUTPUT / "powers.json", "w", encoding="utf-8") as f:
        json.dump(powers, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(powers)} powers -> data/powers.json")


if __name__ == "__main__":
    main()
