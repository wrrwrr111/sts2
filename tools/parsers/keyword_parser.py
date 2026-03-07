"""Parse keywords, intents, orbs, and afflictions from localization JSON and C# source."""
import json
import re
from pathlib import Path
from description_resolver import resolve_description, extract_vars_from_source

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
ORBS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Orbs"
AFFLICTIONS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Afflictions"
MODIFIERS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Modifiers"
OUTPUT = BASE / "data"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def clean_description(text: str) -> str:
    """Strip only non-renderable tags, keep colors and effects for frontend."""
    text = re.sub(r'\[/?(?:thinky_dots|i|font_size)\]', '', text)
    text = re.sub(r'\[rainbow[^\]]*\]', '', text)
    text = re.sub(r'\[font_size=\d+\]', '', text)
    return text


def load_locale_file(locale_dir: Path, filename: str) -> dict:
    loc_file = locale_dir / filename
    if not loc_file.exists():
        return {}
    with open(loc_file, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Keywords ---
def parse_keywords() -> list[dict]:
    loc = load_locale_file(LOCALIZATION_EN, "card_keywords.json")
    loc_zh = load_locale_file(LOCALIZATION_ZH, "card_keywords.json")
    if not loc:
        return []

    keywords = []
    seen = set()
    for key in loc:
        parts = key.split(".")
        kw_id = parts[0]
        if kw_id in seen:
            continue
        seen.add(kw_id)
        title = loc.get(f"{kw_id}.title", kw_id.replace("_", " ").title())
        desc = loc.get(f"{kw_id}.description", "")
        desc_clean = clean_description(desc)
        title_zh = loc_zh.get(f"{kw_id}.title", title)
        desc_zh = loc_zh.get(f"{kw_id}.description", desc)
        desc_clean_zh = clean_description(desc_zh)
        keywords.append({
            "id": kw_id,
            "name": title,
            "description": desc_clean,
            "name_zh": title_zh if title_zh != title else None,
            "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        })
    return keywords


# --- Intents ---
def parse_intents() -> list[dict]:
    loc = load_locale_file(LOCALIZATION_EN, "intents.json")
    loc_zh = load_locale_file(LOCALIZATION_ZH, "intents.json")
    if not loc:
        return []

    intents = []
    seen = set()
    for key in loc:
        parts = key.split(".")
        intent_id = parts[0]
        if intent_id in seen or intent_id.startswith("FORMAT_"):
            continue
        seen.add(intent_id)
        title = loc.get(f"{intent_id}.title", intent_id.replace("_", " ").title())
        desc = loc.get(f"{intent_id}.description", "")
        desc_clean = clean_description(desc)
        title_zh = loc_zh.get(f"{intent_id}.title", title)
        desc_zh = loc_zh.get(f"{intent_id}.description", desc)
        desc_clean_zh = clean_description(desc_zh)
        intents.append({
            "id": intent_id,
            "name": title,
            "description": desc_clean,
            "name_zh": title_zh if title_zh != title else None,
            "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        })
    return intents


# --- Orbs ---
def parse_orbs() -> list[dict]:
    loc = load_locale_file(LOCALIZATION_EN, "orbs.json")
    loc_zh = load_locale_file(LOCALIZATION_ZH, "orbs.json")
    if not loc:
        return []

    orbs = []
    seen = set()
    for key in loc:
        parts = key.split(".")
        orb_id = parts[0]
        if orb_id in seen or orb_id == "EMPTY_SLOT":
            continue
        seen.add(orb_id)

        title = loc.get(f"{orb_id}.title", orb_id.replace("_", " ").title())
        title_zh = loc_zh.get(f"{orb_id}.title", title)

        # Try to get vars from C# source
        all_vars: dict[str, int] = {}
        # Map localization ID back to class name
        orb_class = orb_id.replace("_", "").title().replace(" ", "") + "Orb"
        # Try common names
        for cs_file in ORBS_DIR.glob("*.cs"):
            if cs_file.stem.upper().replace("ORB", "").replace("_", "") == orb_id.replace("_", ""):
                content = cs_file.read_text(encoding="utf-8")
                all_vars = extract_vars_from_source(content)
                # Also extract PassiveVal/EvokeVal
                for m in re.finditer(r'(\w+)Val\s*(?:=>|=)\s*(\d+)', content):
                    var_name = m.group(1)
                    all_vars[var_name] = int(m.group(2))
                break

        desc_raw = loc.get(f"{orb_id}.smartDescription", "")
        if not desc_raw:
            desc_raw = loc.get(f"{orb_id}.description", "")
        desc_resolved = resolve_description(desc_raw, all_vars) if desc_raw else ""
        desc_clean = clean_description(desc_resolved)

        desc_raw_zh = loc_zh.get(f"{orb_id}.smartDescription", "")
        if not desc_raw_zh:
            desc_raw_zh = loc_zh.get(f"{orb_id}.description", desc_raw)
        desc_resolved_zh = resolve_description(desc_raw_zh, all_vars) if desc_raw_zh else ""
        desc_clean_zh = clean_description(desc_resolved_zh)

        orbs.append({
            "id": orb_id,
            "name": title,
            "description": desc_clean,
            "description_raw": desc_raw if desc_raw != desc_clean else None,
            "name_zh": title_zh if title_zh != title else None,
            "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
            "description_raw_zh": desc_raw_zh if desc_raw_zh != desc_raw else None,
        })
    return orbs


# --- Afflictions ---
def parse_afflictions() -> list[dict]:
    loc = load_locale_file(LOCALIZATION_EN, "afflictions.json")
    loc_zh = load_locale_file(LOCALIZATION_ZH, "afflictions.json")
    if not loc:
        return []

    afflictions = []
    seen = set()
    for key in loc:
        parts = key.split(".")
        aff_id = parts[0]
        if aff_id in seen:
            continue
        seen.add(aff_id)

        title = loc.get(f"{aff_id}.title", aff_id.replace("_", " ").title())
        title_zh = loc_zh.get(f"{aff_id}.title", title)

        # Try to get C# source data
        all_vars: dict[str, int] = {}
        is_stackable = False
        has_extra_card_text = False
        for cs_file in AFFLICTIONS_DIR.glob("*.cs"):
            cs_id = class_name_to_id(cs_file.stem)
            if cs_id == aff_id:
                content = cs_file.read_text(encoding="utf-8")
                all_vars = extract_vars_from_source(content)
                is_stackable = "IsStackable => true" in content or "IsStackable = true" in content
                has_extra_card_text = "HasExtraCardText => true" in content or "HasExtraCardText = true" in content
                break

        desc_raw = loc.get(f"{aff_id}.smartDescription", "")
        if not desc_raw:
            desc_raw = loc.get(f"{aff_id}.description", "")
        extra_text_raw = loc.get(f"{aff_id}.extraCardText", "")

        desc_resolved = resolve_description(desc_raw, all_vars) if desc_raw else ""
        desc_clean = clean_description(desc_resolved)
        extra_resolved = resolve_description(extra_text_raw, all_vars) if extra_text_raw else None
        if extra_resolved:
            extra_resolved = clean_description(extra_resolved)

        desc_raw_zh = loc_zh.get(f"{aff_id}.smartDescription", "")
        if not desc_raw_zh:
            desc_raw_zh = loc_zh.get(f"{aff_id}.description", desc_raw)
        extra_text_raw_zh = loc_zh.get(f"{aff_id}.extraCardText", extra_text_raw)
        desc_resolved_zh = resolve_description(desc_raw_zh, all_vars) if desc_raw_zh else ""
        desc_clean_zh = clean_description(desc_resolved_zh)
        extra_resolved_zh = resolve_description(extra_text_raw_zh, all_vars) if extra_text_raw_zh else None
        if extra_resolved_zh:
            extra_resolved_zh = clean_description(extra_resolved_zh)

        afflictions.append({
            "id": aff_id,
            "name": title,
            "description": desc_clean,
            "extra_card_text": extra_resolved,
            "is_stackable": is_stackable,
            "name_zh": title_zh if title_zh != title else None,
            "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
            "extra_card_text_zh": extra_resolved_zh if extra_resolved_zh != extra_resolved else None,
        })
    return afflictions


# --- Modifiers ---
def parse_modifiers() -> list[dict]:
    loc = load_locale_file(LOCALIZATION_EN, "modifiers.json")
    loc_zh = load_locale_file(LOCALIZATION_ZH, "modifiers.json")
    if not loc:
        return []

    modifiers = []
    seen = set()
    for key in loc:
        parts = key.split(".")
        mod_id = parts[0]
        if mod_id in seen:
            continue
        seen.add(mod_id)

        title = loc.get(f"{mod_id}.title", mod_id.replace("_", " ").title())
        title_zh = loc_zh.get(f"{mod_id}.title", title)

        # Try to get C# source data
        all_vars: dict[str, int] = {}
        for cs_file in MODIFIERS_DIR.glob("*.cs"):
            cs_id = class_name_to_id(cs_file.stem)
            if cs_id == mod_id:
                content = cs_file.read_text(encoding="utf-8")
                all_vars = extract_vars_from_source(content)
                break

        desc_raw = loc.get(f"{mod_id}.description", "")
        desc_resolved = resolve_description(desc_raw, all_vars) if desc_raw else ""
        desc_clean = clean_description(desc_resolved)

        desc_raw_zh = loc_zh.get(f"{mod_id}.description", desc_raw)
        desc_resolved_zh = resolve_description(desc_raw_zh, all_vars) if desc_raw_zh else ""
        desc_clean_zh = clean_description(desc_resolved_zh)

        modifiers.append({
            "id": mod_id,
            "name": title,
            "description": desc_clean,
            "name_zh": title_zh if title_zh != title else None,
            "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        })
    return modifiers


# --- Achievements ---
def parse_achievements() -> list[dict]:
    loc = load_locale_file(LOCALIZATION_EN, "achievements.json")
    loc_zh = load_locale_file(LOCALIZATION_ZH, "achievements.json")
    if not loc:
        return []

    achievements = []
    seen = set()
    # Skip meta keys
    skip_prefixes = {"DESCRIPTION_WITH_UNLOCK_TIME", "UNLOCK_DATE", "LOCKED"}
    for key in loc:
        parts = key.split(".")
        ach_id = parts[0]
        if ach_id in seen or ach_id in skip_prefixes:
            continue
        seen.add(ach_id)

        title = loc.get(f"{ach_id}.title", ach_id.replace("_", " ").title())
        desc = loc.get(f"{ach_id}.description", "")
        desc_clean = clean_description(desc)
        title_zh = loc_zh.get(f"{ach_id}.title", title)
        desc_zh = loc_zh.get(f"{ach_id}.description", desc)
        desc_clean_zh = clean_description(desc_zh)

        achievements.append({
            "id": ach_id,
            "name": title,
            "description": desc_clean,
            "name_zh": title_zh if title_zh != title else None,
            "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        })
    return achievements


def main():
    OUTPUT.mkdir(exist_ok=True)

    keywords = parse_keywords()
    with open(OUTPUT / "keywords.json", "w", encoding="utf-8") as f:
        json.dump(keywords, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(keywords)} keywords -> data/keywords.json")

    intents = parse_intents()
    with open(OUTPUT / "intents.json", "w", encoding="utf-8") as f:
        json.dump(intents, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(intents)} intents -> data/intents.json")

    orbs = parse_orbs()
    with open(OUTPUT / "orbs.json", "w", encoding="utf-8") as f:
        json.dump(orbs, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(orbs)} orbs -> data/orbs.json")

    afflictions = parse_afflictions()
    with open(OUTPUT / "afflictions.json", "w", encoding="utf-8") as f:
        json.dump(afflictions, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(afflictions)} afflictions -> data/afflictions.json")

    modifiers = parse_modifiers()
    with open(OUTPUT / "modifiers.json", "w", encoding="utf-8") as f:
        json.dump(modifiers, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(modifiers)} modifiers -> data/modifiers.json")

    achievements = parse_achievements()
    with open(OUTPUT / "achievements.json", "w", encoding="utf-8") as f:
        json.dump(achievements, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(achievements)} achievements -> data/achievements.json")


if __name__ == "__main__":
    main()
