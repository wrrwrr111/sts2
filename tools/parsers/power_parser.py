"""Parse power/buff/debuff data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path
from description_resolver import resolve_description, extract_vars_from_source

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
POWERS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Powers"
OUTPUT = BASE / "data"


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


def get_power_strings(power_id: str, class_name: str, localization: dict) -> tuple[str, str]:
    """Return (title, description_raw) for a power in the given locale."""
    title = localization.get(f"{power_id}.title")
    if title is None:
        title = localization.get(f"{power_id}_POWER.title")
    if title is None:
        full_id = class_name_to_id(class_name)
        title = localization.get(f"{full_id}.title", class_name)

    desc_key = power_id
    if f"{power_id}.smartDescription" not in localization and f"{power_id}.description" not in localization:
        desc_key = f"{power_id}_POWER" if f"{power_id}_POWER.smartDescription" in localization else class_name_to_id(class_name)

    description_raw = localization.get(f"{desc_key}.smartDescription", "")
    if not description_raw:
        description_raw = localization.get(f"{desc_key}.description", "")

    return title, description_raw


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

    # Localization — try both with and without POWER suffix
    title, description_raw = get_power_strings(power_id, class_name, localization)
    title_zh, description_raw_zh = get_power_strings(power_id, class_name, localization_zh)

    description_resolved = resolve_description(description_raw, all_vars) if description_raw else ""
    desc_clean = description_resolved
    description_resolved_zh = resolve_description(description_raw_zh, all_vars) if description_raw_zh else ""
    desc_clean_zh = description_resolved_zh

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
