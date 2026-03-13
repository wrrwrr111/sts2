"""Parse item pool assignments from decompiled C# pool files.

Adds a 'pool' field to potions (cards/relics already carry pool/color metadata).
"""
import json
import re
from path_utils import DECOMPILED, OUTPUT

POTION_POOLS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Models.PotionPools"
EPOCHS_DIR = DECOMPILED / "MegaCrit.Sts2.Core.Timeline.Epochs"


def class_name_to_id(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', s)
    return s.upper()


def pool_name_from_filename(filename: str, suffix: str) -> str:
    """Extract pool name: 'IroncladPotionPool' -> 'ironclad'."""
    name = filename.replace(suffix, "")
    return name.lower()


def extract_model_refs(content: str, pattern: str) -> list[str]:
    """Extract ModelDb references matching a specific pattern."""
    return [class_name_to_id(m.group(1)) for m in re.finditer(pattern, content)]


def extract_epoch_potions(epoch_name: str) -> list[str]:
    """Extract potion IDs from an epoch file that defines Potions property."""
    epoch_file = EPOCHS_DIR / f"{epoch_name}.cs"
    if not epoch_file.exists():
        return []
    content = epoch_file.read_text(encoding="utf-8")
    return extract_model_refs(content, r'ModelDb\.Potion<(\w+)>\(\)')


def parse_potion_pools() -> dict[str, str]:
    """Map potion IDs to their pool names (character association)."""
    potion_to_pool: dict[str, str] = {}

    for filepath in sorted(POTION_POOLS_DIR.glob("*.cs")):
        pool_name = pool_name_from_filename(filepath.stem, "PotionPool")
        if pool_name in ("deprecated", "mock", "token"):
            continue

        content = filepath.read_text(encoding="utf-8")

        potions = extract_model_refs(content, r'ModelDb\.Potion<(\w+)>\(\)')

        # Epoch references (e.g., "return Ironclad4Epoch.Potions;")
        for m in re.finditer(r'(\w+Epoch)\.Potions', content):
            potions.extend(extract_epoch_potions(m.group(1)))

        for potion_id in potions:
            # Character-specific pools take priority over shared
            if potion_id not in potion_to_pool or pool_name != "shared":
                potion_to_pool[potion_id] = pool_name

    return potion_to_pool


def update_potions_with_pools() -> None:
    """Add/refresh the pool field in data/potions.json."""
    potions_file = OUTPUT / "potions.json"
    if not potions_file.exists():
        print("potions.json not found, skipping pool update")
        return

    potion_pools = parse_potion_pools()

    with open(potions_file, "r", encoding="utf-8") as f:
        potions = json.load(f)

    updated = 0
    for potion in potions:
        potion["pool"] = potion_pools.get(potion["id"], "shared")
        updated += 1

    with open(potions_file, "w", encoding="utf-8") as f:
        json.dump(potions, f, indent=2, ensure_ascii=False)

    print(f"Updated {updated} potions with pool assignments")


def main():
    update_potions_with_pools()


if __name__ == "__main__":
    main()
