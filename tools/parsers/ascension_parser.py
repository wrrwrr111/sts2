"""Parse ascension level data from localization JSON."""
import json
import re
from pathlib import Path
from path_utils import LOCALIZATION_EN, LOCALIZATION_ZH, OUTPUT


def load_localization(locale_dir: Path) -> dict:
    loc_file = locale_dir / "ascension.json"
    if loc_file.exists():
        with open(loc_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def parse_all_ascensions() -> list[dict]:
    loc = load_localization(LOCALIZATION_EN)
    loc_zh = load_localization(LOCALIZATION_ZH)

    levels = []
    for key in sorted(loc.keys()):
        m = re.match(r'LEVEL_(\d+)\.title$', key)
        if not m:
            continue
        level = int(m.group(1))
        title = loc[key]
        desc_key = f"LEVEL_{m.group(1)}.description"
        description = loc.get(desc_key, "")
        title_zh = loc_zh.get(key, title)
        description_zh = loc_zh.get(desc_key, description)
        levels.append(
            {
                "id": f"LEVEL_{level:02d}",
                "level": level,
                "name": title,
                "name_zh": title_zh if title_zh != title else None,
                "description": description,
                "description_zh": description_zh if description_zh != description else None,
            }
        )
    return sorted(levels, key=lambda x: x["level"])


def main():
    OUTPUT.mkdir(exist_ok=True)
    ascensions = parse_all_ascensions()
    with open(OUTPUT / "ascensions.json", "w", encoding="utf-8") as f:
        json.dump(ascensions, f, indent=2, ensure_ascii=False)
    print(f"Parsed {len(ascensions)} ascension levels -> data/ascensions.json")


if __name__ == "__main__":
    main()
