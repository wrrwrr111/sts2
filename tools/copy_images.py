"""Copy and organize game images into public/images with md5-based skip cache."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RAW_IMAGES = BASE / "extraction" / "raw" / "images"
STATIC_IMAGES = BASE / "public" / "images"
CACHE_FILE = BASE / "tools" / ".cache" / "copy_images_md5.json"
BASELINE_FILE = BASE / "tools" / ".cache" / "source_images_md5.json"

CARD_PORTRAITS = RAW_IMAGES / "packed" / "card_portraits"
RELICS_SRC = RAW_IMAGES / "relics"
POTIONS_SRC = RAW_IMAGES / "potions"
CHAR_SELECT_SRC = RAW_IMAGES / "packed" / "character_select"
CHAR_ICON_SRC = RAW_IMAGES / "ui" / "top_panel"
MONSTERS_SRC = RAW_IMAGES / "monsters"
ORBS_SRC = RAW_IMAGES / "orbs"

CARDS_DST = STATIC_IMAGES / "cards"
RELICS_DST = STATIC_IMAGES / "relics"
POTIONS_DST = STATIC_IMAGES / "potions"
CHARS_DST = STATIC_IMAGES / "characters"
MONSTERS_DST = STATIC_IMAGES / "monsters"
ORBS_DST = STATIC_IMAGES / "orbs"
ICONS_SRC = RAW_IMAGES / "packed" / "sprite_fonts"
ICONS_DST = STATIC_IMAGES / "icons"
ANCIENTS_SRC = RAW_IMAGES / "ui" / "run_history"
ANCIENTS_DST = STATIC_IMAGES / "misc" / "ancients"
BOSSES_DST = STATIC_IMAGES / "misc" / "bosses"
CARD_OVERLAYS_SRC = RAW_IMAGES / "card_overlays"
CARD_OVERLAYS_DST = STATIC_IMAGES / "card_overlays"


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CopyCache:
    def __init__(self, path: Path, baseline_md5: dict[str, str] | None = None):
        self.path = path
        self.entries = self._load()
        self.baseline_md5 = baseline_md5 or {}
        self.seeded_from_baseline = 0

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        files = payload.get("files")
        if not isinstance(files, dict):
            return {}
        return {
            key: value
            for key, value in files.items()
            if isinstance(key, str) and isinstance(value, dict)
        }

    def copy_if_changed(self, src: Path, dst: Path) -> bool:
        dst_key = dst.relative_to(BASE).as_posix()
        src_key = src.relative_to(BASE).as_posix()
        dst_rel = dst.relative_to(STATIC_IMAGES).as_posix()
        src_hash = file_md5(src)

        entry = self.entries.get(dst_key)
        # If source hash is unchanged and destination exists, skip recopy.
        if (
            entry
            and entry.get("source_md5") == src_hash
            and entry.get("source") == src_key
            and dst.exists()
        ):
            return False

        baseline_hash = self.baseline_md5.get(dst_rel)
        if entry is None and baseline_hash and dst.exists():
            # First run with baseline: keep already-compressed output untouched.
            current_dst_hash = file_md5(dst)
            src_mtime = src.stat().st_mtime
            dst_mtime = dst.stat().st_mtime
            if current_dst_hash == baseline_hash and src_mtime <= dst_mtime:
                self.entries[dst_key] = {
                    "source": src_key,
                    "source_md5": src_hash,
                    "copied_at": datetime.now().isoformat(timespec="seconds"),
                    "seeded_from_baseline": True,
                }
                self.seeded_from_baseline += 1
                return False

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        self.entries[dst_key] = {
            "source": src_key,
            "source_md5": src_hash,
            "copied_at": datetime.now().isoformat(timespec="seconds"),
        }
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "files": self.entries}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_baseline_md5(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        return {}
    return {k: v for k, v in files.items() if isinstance(k, str) and isinstance(v, str)}


def copy_cards(cache: CopyCache):
    """Copy card portraits, separating beta art into a beta/ subfolder."""
    CARDS_DST.mkdir(parents=True, exist_ok=True)
    beta_dst = CARDS_DST / "beta"
    beta_dst.mkdir(parents=True, exist_ok=True)
    count = 0
    beta_count = 0
    skipped = 0
    beta_skipped = 0
    # Top-level pngs (e.g. ancient_beta.png, beta.png)
    for png in CARD_PORTRAITS.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, CARDS_DST / png.name):
            count += 1
        else:
            skipped += 1
    # Subdirectory pngs — separate beta from non-beta
    for png in CARD_PORTRAITS.rglob("*.png"):
        if png.name.endswith(".import"):
            continue
        if png.parent == CARD_PORTRAITS:
            continue  # already handled above
        if "beta" in png.parent.name:
            if cache.copy_if_changed(png, beta_dst / png.name):
                beta_count += 1
            else:
                beta_skipped += 1
        else:
            if cache.copy_if_changed(png, CARDS_DST / png.name):
                count += 1
            else:
                skipped += 1
    print(f"Copied {count} card images -> static/images/cards/ (skipped {skipped})")
    print(f"Copied {beta_count} beta card images -> static/images/cards/beta/ (skipped {beta_skipped})")


def copy_relics(cache: CopyCache):
    RELICS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in RELICS_SRC.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, RELICS_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} relic images -> static/images/relics/ (skipped {skipped})")


def copy_potions(cache: CopyCache):
    POTIONS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in POTIONS_SRC.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, POTIONS_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} potion images -> static/images/potions/ (skipped {skipped})")


def copy_characters(cache: CopyCache):
    CHARS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    # char_select images
    for png in CHAR_SELECT_SRC.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, CHARS_DST / png.name):
            count += 1
        else:
            skipped += 1
    # character_icon images
    for png in CHAR_ICON_SRC.glob("character_icon_*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, CHARS_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} character images -> static/images/characters/ (skipped {skipped})")


def copy_monsters(cache: CopyCache):
    MONSTERS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in MONSTERS_SRC.rglob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, MONSTERS_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} monster images -> static/images/monsters/ (skipped {skipped})")


def copy_orbs(cache: CopyCache):
    ORBS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in ORBS_SRC.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, ORBS_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} orb images -> static/images/orbs/ (skipped {skipped})")


def copy_icons(cache: CopyCache):
    ICONS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in ICONS_SRC.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, ICONS_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} icon images -> static/images/icons/ (skipped {skipped})")


def copy_ancients(cache: CopyCache):
    ANCIENTS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    ANCIENT_NAMES = {"darv", "neow", "nonupeipe", "orobas", "pael", "tanx", "tezcatara", "vakuu"}
    for png in ANCIENTS_SRC.glob("*.png"):
        if png.name.endswith(".import"):
            continue
        if png.stem in ANCIENT_NAMES:
            if cache.copy_if_changed(png, ANCIENTS_DST / png.name):
                count += 1
            else:
                skipped += 1
    print(f"Copied {count} ancient icons -> static/images/misc/ancients/ (skipped {skipped})")


def copy_bosses(cache: CopyCache):
    BOSSES_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in ANCIENTS_SRC.glob("*_boss.png"):
        if png.name.endswith(".import"):
            continue
        if cache.copy_if_changed(png, BOSSES_DST / png.name):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} boss icons -> static/images/misc/bosses/ (skipped {skipped})")

def copy_card_overlays(cache: CopyCache):
    CARD_OVERLAYS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for png in CARD_OVERLAYS_SRC.rglob("*.png"):
        if png.name.endswith(".import"):
            continue
        rel = png.relative_to(CARD_OVERLAYS_SRC)
        dest = CARD_OVERLAYS_DST / rel
        if cache.copy_if_changed(png, dest):
            count += 1
        else:
            skipped += 1
    print(f"Copied {count} card overlay images -> static/images/card_overlays/ (skipped {skipped})")


def main():
    print("=== Copying game images to static directory ===\n")
    baseline_md5 = load_baseline_md5(BASELINE_FILE)
    cache = CopyCache(CACHE_FILE, baseline_md5=baseline_md5)
    copy_cards(cache)
    copy_relics(cache)
    copy_potions(cache)
    copy_characters(cache)
    copy_monsters(cache)
    copy_icons(cache)
    copy_orbs(cache)
    copy_ancients(cache)
    copy_bosses(cache)
    copy_card_overlays(cache)
    cache.save()
    print(f"\nSaved md5 copy cache -> {CACHE_FILE}")
    if baseline_md5:
        print(f"Loaded baseline md5 -> {BASELINE_FILE} ({len(baseline_md5)} files)")
        print(f"Seeded from baseline -> {cache.seeded_from_baseline} files")
    print("\n=== Done! ===")


if __name__ == "__main__":
    main()
