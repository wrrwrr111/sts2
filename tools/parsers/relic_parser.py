"""Parse relic data from decompiled C# files and localization JSON."""
import json
import re
from pathlib import Path
from description_resolver import resolve_description, extract_vars_from_source

BASE = Path(__file__).resolve().parents[2]
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
RELICS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.Relics"
RELIC_POOLS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.RelicPools"
STATIC_IMAGES = BASE / "public" / "images" / "relics"
OUTPUT = BASE / "data"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "relics.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_relic_pools() -> dict[str, str]:
    """Map relic class names to character pools."""
    relic_to_pool = {}
    pool_map = {
        "IroncladRelicPool.cs": "ironclad",
        "SilentRelicPool.cs": "silent",
        "DefectRelicPool.cs": "defect",
        "NecrobinderRelicPool.cs": "necrobinder",
        "RegentRelicPool.cs": "regent",
        "SharedRelicPool.cs": "shared",
    }
    for filename, pool_name in pool_map.items():
        filepath = RELIC_POOLS_DIR / filename
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8")
        for m in re.finditer(r'ModelDb\.Relic<(\w+)>\(\)', content):
            relic_to_pool[m.group(1)] = pool_name
    return relic_to_pool


def parse_single_relic(filepath: Path, localization: dict, localization_zh: dict, relic_pools: dict) -> dict | None:
    content = filepath.read_text(encoding="utf-8")
    class_name = filepath.stem

    if class_name.startswith("Deprecated") or class_name.startswith("Mock"):
        return None

    relic_id = class_name_to_id(class_name)

    # Rarity
    rarity_match = re.search(r'Rarity\s*=>\s*RelicRarity\.(\w+)', content)
    rarity = rarity_match.group(1) if rarity_match else "Unknown"

    # Extract variable values from source
    all_vars = extract_vars_from_source(content)

    # Localization
    title = localization.get(f"{relic_id}.title", class_name)
    description_raw = localization.get(f"{relic_id}.description", "")
    flavor = localization.get(f"{relic_id}.flavor", "")
    title_zh = localization_zh.get(f"{relic_id}.title", title)
    description_raw_zh = localization_zh.get(f"{relic_id}.description", description_raw)
    flavor_zh = localization_zh.get(f"{relic_id}.flavor", flavor)

    # Resolve templates, keep color tags for frontend rendering
    description_resolved = resolve_description(description_raw, all_vars)
    desc_clean = description_resolved
    flavor_clean = flavor
    description_resolved_zh = resolve_description(description_raw_zh, all_vars)
    desc_clean_zh = description_resolved_zh
    flavor_clean_zh = flavor_zh

    # Pool/character
    pool = relic_pools.get(class_name, "shared")

    # Image URL
    image_file = STATIC_IMAGES / f"{relic_id.lower()}.png"
    image_url = f"/images/relics/{relic_id.lower()}.png" if image_file.exists() else None

    return {
        "id": relic_id,
        "name": title,
        "name_zh": title_zh if title_zh != title else None,
        "description": desc_clean,
        "description_zh": desc_clean_zh if desc_clean_zh != desc_clean else None,
        "description_raw": description_raw,
        "description_raw_zh": description_raw_zh if description_raw_zh != description_raw else None,
        "flavor": flavor_clean,
        "flavor_zh": flavor_clean_zh if flavor_clean_zh != flavor_clean else None,
        "rarity": rarity,
        "pool": pool,
        "image_url": image_url,
    }


def parse_all_relics() -> list[dict]:
    localization = load_localization(LOCALIZATION_EN)
    localization_zh = load_localization(LOCALIZATION_ZH)
    relic_pools = parse_relic_pools()
    relics = []
    for filepath in sorted(RELICS_DIR.glob("*.cs")):
        relic = parse_single_relic(filepath, localization, localization_zh, relic_pools)
        if relic:
            relics.append(relic)
    return relics


def main():
    OUTPUT.mkdir(exist_ok=True)
    relics = parse_all_relics()
    with open(OUTPUT / "relics.json", "w", encoding="utf-8") as f:
        json.dump(relics, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(relics)} relics -> data/relics.json")


if __name__ == "__main__":
    main()
