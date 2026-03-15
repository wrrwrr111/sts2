#!/usr/bin/env python3
"""
Compare two versions of Spire Codex data and generate a changelog.

Usage:
  # Compare current data against a git tag/commit:
  python3 tools/diff_data.py v0.9.1

  # Compare two git refs:
  python3 tools/diff_data.py v0.9.1 v0.9.2

  # Compare two directories:
  python3 tools/diff_data.py /path/to/old/data /path/to/new/data

  # Output as markdown:
  python3 tools/diff_data.py v0.9.1 --format md > changelog.md

  # Save as JSON changelog for a game update:
  python3 tools/diff_data.py v0.9.1 --format json \\
      --game-version "0.98.2" --build-id "22238966" \\
      --date "2026-03-09" --title "March Update"

  # Save as JSON changelog for a Codex parser/feature update (same game version):
  python3 tools/diff_data.py v0.9.1 --format json \\
      --game-version "0.98.2" --build-id "22238966" \\
      --codex-version 2 --title "Improved card descriptions"

  # Save both markdown + json diff report files (name includes game version if found):
  python3 tools/diff_data.py v0.9.1 --record

  # Custom report output location/name:
  python3 tools/diff_data.py v0.9.1 --record \\
      --out-dir reports/diff --report-name 2026-03-13_patch-notes

Options:
  --game-version    The game's version string from Steam (e.g. "0.98.2").
                    If omitted, tries to auto-detect from extraction/raw/release_info.json.
  --build-id        Steam build ID (e.g. "22238966") — changes with each depot update
  --codex-version   Codex revision number for parser/feature updates on the same game
                    version. Omit for game updates, set to 1/2/3/... for codex updates.
                    Output filename becomes {game_version}-codex{N}.json
  --date            Date of the update (defaults to today)
  --title           Human-readable title for this changelog entry
  --record          Also write markdown + json diff files to reports/diff
  --out-dir         Output directory used with --record (default: reports/diff)
  --report-name     Output filename (without extension) used with --record

  The Steam App ID for Slay the Spire 2 is 2868840 (hardcoded).
  Build IDs can be found on SteamDB or via Steam's app info API.
"""
import json
import sys
import subprocess
import tempfile
import shutil
import io
import re
from datetime import datetime, date as d
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "diff"
RELEASE_INFO_PATH = Path(__file__).resolve().parent.parent / "extraction" / "raw" / "release_info.json"

# Slay the Spire 2 Steam App ID (fixed)
STEAM_APP_ID = 2868840

# Fields to ignore when diffing (noise / internal)
IGNORE_FIELDS = {"image_url", "beta_image_url", "sort_order", "era_position"}

# Human-readable category names
CATEGORY_NAMES = {
    "cards": "Cards",
    "characters": "Characters",
    "relics": "Relics",
    "monsters": "Monsters",
    "potions": "Potions",
    "enchantments": "Enchantments",
    "encounters": "Encounters",
    "events": "Events",
    "powers": "Powers",
    "keywords": "Keywords",
    "intents": "Intents",
    "orbs": "Orbs",
    "afflictions": "Afflictions",
    "modifiers": "Modifiers",
    "achievements": "Achievements",
    "epochs": "Epochs",
    "stories": "Stories",
}

# Files under data/ that are not entity lists.
SKIP_CATEGORY_FILES = {"ui_atlas", "changelogs"}

# Key fields to show in "changed" summaries (beyond just the id)
DISPLAY_FIELDS = {
    "cards": ["name", "cost", "damage", "block", "type", "rarity"],
    "relics": ["name", "rarity"],
    "monsters": ["name", "min_hp", "max_hp"],
    "potions": ["name", "rarity"],
    "powers": ["name", "type"],
    "enchantments": ["name"],
    "encounters": ["name", "act"],
    "events": ["name", "type"],
    "epochs": ["title", "era"],
}


def load_json_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def discover_categories(old_dir: Path, new_dir: Path) -> list[str]:
    """Find comparable entity category files in both directories."""
    categories = {
        p.stem
        for root in (old_dir, new_dir)
        for p in root.glob("*.json")
        if p.stem not in SKIP_CATEGORY_FILES
    }
    preferred = [key for key in CATEGORY_NAMES if key in categories]
    extras = sorted(key for key in categories if key not in CATEGORY_NAMES)
    return preferred + extras


def category_name(key: str) -> str:
    return CATEGORY_NAMES.get(key, key.replace("_", " ").title())


def entity_key(entity: dict) -> str | None:
    for key in ("id", "key", "name", "title"):
        val = entity.get(key)
        if val is not None and str(val).strip():
            return str(val)
    return None


def extract_git_data(ref: str, tmp_dir: Path) -> Path:
    """Extract data/ files from a git ref into a temp directory."""
    out = tmp_dir / ref.replace("/", "_")
    out.mkdir(parents=True, exist_ok=True)
    # List data files at that ref
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "data/"],
        capture_output=True, text=True, cwd=DATA_DIR.parent
    )
    if result.returncode != 0:
        print(f"Error: Could not read git ref '{ref}': {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    for line in result.stdout.strip().split("\n"):
        if not line.endswith(".json"):
            continue
        fname = Path(line).name
        content = subprocess.run(
            ["git", "show", f"{ref}:{line}"],
            capture_output=True, text=True, cwd=DATA_DIR.parent
        )
        if content.returncode == 0:
            (out / fname).write_text(content.stdout, encoding="utf-8")
    return out


def diff_entity(old: dict, new: dict) -> dict[str, tuple]:
    """Return changed fields between two entities."""
    changes = {}
    all_keys = set(old.keys()) | set(new.keys())
    for key in all_keys:
        if key in IGNORE_FIELDS:
            continue
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = (old_val, new_val)
    return changes


def diff_category(old_data: list[dict], new_data: list[dict]) -> dict:
    """Diff a single category and return added/removed/changed."""
    old_map = {}
    for entity in old_data:
        key = entity_key(entity)
        if key is not None:
            old_map[key] = entity
    new_map = {}
    for entity in new_data:
        key = entity_key(entity)
        if key is not None:
            new_map[key] = entity

    old_ids = set(old_map.keys())
    new_ids = set(new_map.keys())

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)

    changed = {}
    for eid in sorted(old_ids & new_ids):
        field_changes = diff_entity(old_map[eid], new_map[eid])
        if field_changes:
            changed[eid] = {
                "name": new_map[eid].get("name") or new_map[eid].get("title", eid),
                "changes": field_changes,
            }

    return {
        "added": [(eid, new_map[eid]) for eid in added],
        "removed": [(eid, old_map[eid]) for eid in removed],
        "changed": changed,
        "old_count": len(old_data),
        "new_count": len(new_data),
    }


def format_value(val) -> str:
    """Format a value for display."""
    if val is None:
        return "none"
    if isinstance(val, bool):
        return "yes" if val else "no"
    if isinstance(val, list):
        if len(val) == 0:
            return "[]"
        if len(val) <= 5:
            return ", ".join(str(v) for v in val)
        return f"{len(val)} items"
    if isinstance(val, dict):
        return f"{len(val)} fields"
    if isinstance(val, str) and len(val) > 80:
        return val[:77] + "..."
    return str(val)


def entity_name(entity: dict) -> str:
    return entity.get("name") or entity.get("title") or entity.get("id", "?")


def ordered_result_categories(results: dict) -> list[str]:
    preferred = [key for key in CATEGORY_NAMES if key in results]
    extras = sorted(key for key in results if key not in CATEGORY_NAMES)
    return preferred + extras


def print_text(results: dict, old_label: str, new_label: str):
    """Print changelog in plain text."""
    print(f"Spire Codex Data Changelog")
    print(f"  {old_label}  →  {new_label}")
    print(f"{'=' * 60}\n")

    total_added = total_removed = total_changed = 0

    for cat_key in ordered_result_categories(results):
        cat_name = category_name(cat_key)
        diff = results[cat_key]
        n_added = len(diff["added"])
        n_removed = len(diff["removed"])
        n_changed = len(diff["changed"])
        if n_added == 0 and n_removed == 0 and n_changed == 0:
            continue

        total_added += n_added
        total_removed += n_removed
        total_changed += n_changed

        count_change = ""
        if diff["old_count"] != diff["new_count"]:
            count_change = f"  ({diff['old_count']} → {diff['new_count']})"
        print(f"── {cat_name}{count_change} ──")

        if diff["added"]:
            print(f"  + Added ({n_added}):")
            for eid, entity in diff["added"]:
                extras = []
                for field in DISPLAY_FIELDS.get(cat_key, []):
                    val = entity.get(field)
                    if val is not None:
                        extras.append(f"{field}={format_value(val)}")
                extra_str = f"  ({', '.join(extras)})" if extras else ""
                print(f"    + {entity_name(entity)}{extra_str}")

        if diff["removed"]:
            print(f"  - Removed ({n_removed}):")
            for eid, entity in diff["removed"]:
                print(f"    - {entity_name(entity)}")

        if diff["changed"]:
            print(f"  ~ Changed ({n_changed}):")
            for eid, info in diff["changed"].items():
                changes = info["changes"]
                print(f"    ~ {info['name']}:")
                for field, (old_val, new_val) in changes.items():
                    print(f"        {field}: {format_value(old_val)} → {format_value(new_val)}")

        print()

    print(f"{'=' * 60}")
    print(f"Summary: +{total_added} added, -{total_removed} removed, ~{total_changed} changed")


def print_markdown(results: dict, old_label: str, new_label: str):
    """Print changelog in markdown."""
    print(f"# Spire Codex Changelog")
    print(f"**{old_label}** → **{new_label}**\n")

    total_added = total_removed = total_changed = 0

    for cat_key in ordered_result_categories(results):
        cat_name = category_name(cat_key)
        diff = results[cat_key]
        n_added = len(diff["added"])
        n_removed = len(diff["removed"])
        n_changed = len(diff["changed"])
        if n_added == 0 and n_removed == 0 and n_changed == 0:
            continue

        total_added += n_added
        total_removed += n_removed
        total_changed += n_changed

        count_change = ""
        if diff["old_count"] != diff["new_count"]:
            count_change = f" ({diff['old_count']} → {diff['new_count']})"
        print(f"## {cat_name}{count_change}\n")

        if diff["added"]:
            print(f"### Added ({n_added})")
            for eid, entity in diff["added"]:
                extras = []
                for field in DISPLAY_FIELDS.get(cat_key, []):
                    val = entity.get(field)
                    if val is not None:
                        extras.append(f"{field}: {format_value(val)}")
                extra_str = f" — {', '.join(extras)}" if extras else ""
                print(f"- **{entity_name(entity)}**{extra_str}")
            print()

        if diff["removed"]:
            print(f"### Removed ({n_removed})")
            for eid, entity in diff["removed"]:
                print(f"- ~~{entity_name(entity)}~~")
            print()

        if diff["changed"]:
            print(f"### Changed ({n_changed})")
            for eid, info in diff["changed"].items():
                changes = info["changes"]
                change_strs = []
                for field, (old_val, new_val) in changes.items():
                    change_strs.append(f"`{field}`: {format_value(old_val)} → {format_value(new_val)}")
                print(f"- **{info['name']}**: {'; '.join(change_strs)}")
            print()

    print(f"---\n**Summary:** +{total_added} added, -{total_removed} removed, ~{total_changed} changed")


def build_json_output(results: dict, game_version: str, build_id: str, codex_version: str, date: str, title: str, old_label: str, new_label: str) -> dict:
    """Build a JSON-serializable changelog object."""
    categories = []
    total_added = total_removed = total_changed = 0

    for cat_key in ordered_result_categories(results):
        cat_name = category_name(cat_key)
        diff = results[cat_key]
        n_added = len(diff["added"])
        n_removed = len(diff["removed"])
        n_changed = len(diff["changed"])
        if n_added == 0 and n_removed == 0 and n_changed == 0:
            continue

        total_added += n_added
        total_removed += n_removed
        total_changed += n_changed

        cat_entry = {
            "id": cat_key,
            "name": cat_name,
            "old_count": diff["old_count"],
            "new_count": diff["new_count"],
        }

        if diff["added"]:
            cat_entry["added"] = []
            for eid, entity in diff["added"]:
                entry = {"id": eid, "name": entity_name(entity)}
                for field in DISPLAY_FIELDS.get(cat_key, []):
                    val = entity.get(field)
                    if val is not None:
                        entry[field] = val
                cat_entry["added"].append(entry)

        if diff["removed"]:
            cat_entry["removed"] = [
                {"id": eid, "name": entity_name(entity)}
                for eid, entity in diff["removed"]
            ]

        if diff["changed"]:
            cat_entry["changed"] = []
            for eid, info in diff["changed"].items():
                changes = []
                for field, (old_val, new_val) in info["changes"].items():
                    changes.append({
                        "field": field,
                        "old": format_value(old_val),
                        "new": format_value(new_val),
                    })
                cat_entry["changed"].append({
                    "id": eid,
                    "name": info["name"],
                    "changes": changes,
                })

        categories.append(cat_entry)

    # Build the tag: "0.98.2" for game updates, "0.98.2-codex2" for codex updates
    tag = f"{game_version}-codex{codex_version}" if codex_version else game_version

    return {
        "app_id": STEAM_APP_ID,
        "game_version": game_version,
        "build_id": build_id,
        "codex_version": int(codex_version) if codex_version else None,
        "tag": tag,
        "date": date,
        "title": title,
        "from_ref": old_label,
        "to_ref": new_label,
        "summary": {
            "added": total_added,
            "removed": total_removed,
            "changed": total_changed,
        },
        "categories": categories,
    }


def parse_named_arg(argv: list[str], name: str, default: str = "") -> tuple[str, list[str]]:
    """Extract a --name value pair from argv, return (value, remaining_argv)."""
    if name in argv:
        idx = argv.index(name)
        if idx + 1 < len(argv):
            val = argv[idx + 1]
            return val, argv[:idx] + argv[idx + 2:]
        return default, argv[:idx]
    return default, argv


def parse_flag(argv: list[str], name: str) -> tuple[bool, list[str]]:
    if name in argv:
        idx = argv.index(name)
        return True, argv[:idx] + argv[idx + 1:]
    return False, argv


def sanitize_label(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "diff"


def normalize_game_version(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.lower().startswith("v") and len(value) > 1 and value[1].isdigit():
        return value[1:]
    return value


def parse_version_from_release_info_text(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    version = payload.get("version")
    if not isinstance(version, str):
        return ""
    return normalize_game_version(version)


def detect_game_version_from_local_release_info() -> str:
    if not RELEASE_INFO_PATH.exists():
        return ""
    try:
        return parse_version_from_release_info_text(RELEASE_INFO_PATH.read_text(encoding="utf-8"))
    except OSError:
        return ""


def detect_game_version_from_git_ref(ref: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:extraction/raw/release_info.json"],
        capture_output=True, text=True, cwd=DATA_DIR.parent
    )
    if result.returncode != 0:
        return ""
    return parse_version_from_release_info_text(result.stdout)


def detect_game_version_from_label(label: str) -> str:
    match = re.search(r"v?\d+\.\d+\.\d+(?:[-._][A-Za-z0-9]+)?", label)
    if not match:
        return ""
    return normalize_game_version(match.group(0))


def resolve_game_version(input_version: str, new_label: str, new_ref: str | None, new_is_current: bool) -> tuple[str, str]:
    """Resolve game version from explicit input or best-effort auto detection."""
    if input_version:
        return normalize_game_version(input_version), "input"

    # Prefer the compared "new" ref when diffing two git refs.
    if new_ref:
        ref_version = detect_game_version_from_git_ref(new_ref)
        if ref_version:
            return ref_version, "git_release_info"

    # For current workspace comparisons, read local extraction release_info.
    if new_is_current:
        local_version = detect_game_version_from_local_release_info()
        if local_version:
            return local_version, "local_release_info"

    # Last resort: try to parse semantic version from label itself.
    label_version = detect_game_version_from_label(new_label)
    if label_version:
        return label_version, "label"

    return "", "unknown"


def summarize(results: dict) -> dict[str, int]:
    added = removed = changed = 0
    for diff in results.values():
        added += len(diff["added"])
        removed += len(diff["removed"])
        changed += len(diff["changed"])
    return {"added": added, "removed": removed, "changed": changed}


def serialize_results(results: dict) -> list[dict]:
    categories = []
    for cat_key in ordered_result_categories(results):
        diff = results[cat_key]
        n_added = len(diff["added"])
        n_removed = len(diff["removed"])
        n_changed = len(diff["changed"])
        if n_added == 0 and n_removed == 0 and n_changed == 0:
            continue

        cat_entry = {
            "id": cat_key,
            "name": category_name(cat_key),
            "old_count": diff["old_count"],
            "new_count": diff["new_count"],
            "added": [
                {"id": eid, "name": entity_name(entity), "entity": entity}
                for eid, entity in diff["added"]
            ],
            "removed": [
                {"id": eid, "name": entity_name(entity), "entity": entity}
                for eid, entity in diff["removed"]
            ],
            "changed": [],
        }
        for eid, info in diff["changed"].items():
            cat_entry["changed"].append({
                "id": eid,
                "name": info["name"],
                "changes": [
                    {"field": field, "old": old_val, "new": new_val}
                    for field, (old_val, new_val) in info["changes"].items()
                ],
            })
        categories.append(cat_entry)
    return categories


def markdown_text(results: dict, old_label: str, new_label: str) -> str:
    buff = io.StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = buff
        print_markdown(results, old_label, new_label)
    finally:
        sys.stdout = stdout
    return buff.getvalue()


def main():
    argv = sys.argv[1:]
    fmt, argv = parse_named_arg(argv, "--format", "text")
    game_version_input, argv = parse_named_arg(argv, "--game-version", "")
    build_id, argv = parse_named_arg(argv, "--build-id", "")
    codex_version, argv = parse_named_arg(argv, "--codex-version", "")
    date, argv = parse_named_arg(argv, "--date", "")
    title, argv = parse_named_arg(argv, "--title", "")
    out_dir, argv = parse_named_arg(argv, "--out-dir", str(REPORTS_DIR))
    report_name, argv = parse_named_arg(argv, "--report-name", "")
    record, argv = parse_flag(argv, "--record")
    args = [a for a in argv if not a.startswith("--")]

    if len(args) == 0:
        print(__doc__)
        sys.exit(0)

    tmp_dir = None
    new_ref_for_version = None
    new_is_current = False

    if len(args) == 1:
        old_ref = args[0]
        new_dir = DATA_DIR
        new_label = "current"
        new_is_current = True
        tmp_dir = Path(tempfile.mkdtemp())
        old_dir = extract_git_data(old_ref, tmp_dir)
        old_label = old_ref
    elif len(args) == 2:
        old_path = Path(args[0])
        new_path = Path(args[1])
        if old_path.is_dir() and new_path.is_dir():
            old_dir = old_path
            new_dir = new_path
            old_label = str(old_path)
            new_label = str(new_path)
        else:
            tmp_dir = Path(tempfile.mkdtemp())
            old_dir = extract_git_data(args[0], tmp_dir)
            new_dir = extract_git_data(args[1], tmp_dir)
            old_label = args[0]
            new_label = args[1]
            new_ref_for_version = args[1]
    else:
        print("Usage: tools/diff_data.py <old_ref> [new_ref] [--format text|md|json] [--game-version X] [--build-id Y] [--codex-version N] [--date Z] [--title T]", file=sys.stderr)
        sys.exit(1)

    try:
        results = {}
        for cat_key in discover_categories(old_dir, new_dir):
            old_file = old_dir / f"{cat_key}.json"
            new_file = new_dir / f"{cat_key}.json"
            old_data = load_json_file(old_file)
            new_data = load_json_file(new_file)
            if old_data or new_data:
                results[cat_key] = diff_category(old_data, new_data)

        game_version, game_version_source = resolve_game_version(
            input_version=game_version_input,
            new_label=new_label,
            new_ref=new_ref_for_version,
            new_is_current=new_is_current,
        )
        if game_version and (fmt == "json" or record):
            print(f"Using game version: {game_version} (source: {game_version_source})")

        if fmt == "md":
            print_markdown(results, old_label, new_label)
        elif fmt == "json":
            if not game_version:
                game_version = normalize_game_version(new_label) or "unknown"
            if not date:
                date = d.today().isoformat()
            if not title:
                title = f"Update {game_version}" + (f" (Codex {codex_version})" if codex_version else "")
            changelog = build_json_output(results, game_version, build_id, codex_version, date, title, old_label, new_label)
            # Save to changelogs directory — keyed by tag
            tag = changelog["tag"]
            out_path = DATA_DIR / "changelogs" / f"{tag}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(changelog, f, indent=2, ensure_ascii=False)
            print(f"Saved changelog to {out_path}")
            # Also print to stdout
            print(json.dumps(changelog["summary"], indent=2))
        else:
            print_text(results, old_label, new_label)

        if record:
            now = datetime.now().strftime("%Y-%m-%d")
            if not report_name:
                if game_version:
                    tag = f"{game_version}-codex{codex_version}" if codex_version else game_version
                    report_name = f"{tag}_{sanitize_label(old_label)}_to_{sanitize_label(new_label)}"
                else:
                    report_name = f"{now}_{sanitize_label(old_label)}_to_{sanitize_label(new_label)}"
            out_base = Path(out_dir).expanduser().resolve()
            out_base.mkdir(parents=True, exist_ok=True)

            md_path = out_base / f"{report_name}.md"
            json_path = out_base / f"{report_name}.json"

            md_path.write_text(markdown_text(results, old_label, new_label), encoding="utf-8")
            record_payload = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "from_ref": old_label,
                "to_ref": new_label,
                "game_version": game_version or None,
                "game_version_source": game_version_source,
                "summary": summarize(results),
                "categories": serialize_results(results),
            }
            json_path.write_text(
                json.dumps(record_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Saved record files:\n- {md_path}\n- {json_path}")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
