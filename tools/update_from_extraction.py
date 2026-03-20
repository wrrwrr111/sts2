#!/usr/bin/env python3
"""Run the full local update pipeline after replacing extraction/ files."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_INFO = ROOT / "extraction" / "raw" / "release_info.json"
STATE_FILE = ROOT / "tools" / ".cache" / "update_state.json"
VERSION_PATTERN = re.compile(r"v?\d+\.\d+\.\d+(?:[-._][A-Za-z0-9]+)?")


def run_step(cmd: list[str]) -> None:
    print(f"\n$ {shlex.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def ensure_path(path: Path, hint: str) -> None:
    if not path.exists():
        print(f"Error: missing {path}\nHint: {hint}", file=sys.stderr)
        sys.exit(1)


def normalize_version(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("v") and len(value) > 1 and value[1].isdigit():
        return value[1:]
    return value


def parse_version_text(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    version = payload.get("version")
    if not isinstance(version, str):
        return ""
    return normalize_version(version)


def read_version_from_file(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return parse_version_text(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def read_version_from_ref(ref: str) -> str:
    match = VERSION_PATTERN.search(ref.strip())
    if not match:
        return ""
    return normalize_version(match.group(0))


def read_version_from_latest_report(out_dir: Path) -> str:
    if not out_dir.exists():
        return ""
    report_files: list[tuple[float, Path]] = []
    for path in out_dir.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        report_files.append((mtime, path))
    report_files.sort(key=lambda item: item[0], reverse=True)

    for _, report_file in report_files:
        try:
            payload = json.loads(report_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        version = payload.get("game_version")
        if isinstance(version, str) and version.strip():
            return normalize_version(version)
    return ""


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update data/images/diff after refreshing extraction/ content."
    )
    parser.add_argument(
        "--old-ref",
        default="",
        help="Old git ref/tag/commit used for diff comparison. Default: HEAD",
    )
    parser.add_argument(
        "--game-version",
        default="",
        help="Override game version for diff output (otherwise detect from local release_info, state, or latest diff report).",
    )
    parser.add_argument(
        "--report-name",
        default="",
        help="Custom diff report filename (without extension).",
    )
    parser.add_argument(
        "--out-dir",
        default="reports/diff",
        help="Diff report output directory. Default: reports/diff",
    )
    parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Skip diff generation.",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip copying image assets.",
    )
    parser.add_argument(
        "--skip-compress",
        action="store_true",
        help="Skip image compression.",
    )
    parser.add_argument(
        "--compress-max",
        type=int,
        default=300,
        help="Max image size (KB) for compress_images.py. Default: 300",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=90,
        help="JPEG/WebP quality for compress_images.py. Default: 90",
    )
    parser.add_argument(
        "--png-colors",
        type=int,
        default=0,
        help="PNG quantization colors. 0 keeps original. Default: 0",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run pipeline even if game version is unchanged vs HEAD.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    ensure_path(ROOT / "extraction" / "decompiled", "Place fresh decompiled files under extraction/decompiled.")
    ensure_path(
        ROOT / "extraction" / "raw",
        "Place fresh extracted raw files under extraction/raw.",
    )

    current_version = normalize_version(args.game_version.strip()) if args.game_version.strip() else ""
    if not current_version:
        current_version = read_version_from_file(RELEASE_INFO)

    old_ref = args.old_ref or "HEAD"
    report_dir = Path(args.out_dir).expanduser().resolve()

    state = load_state(STATE_FILE)
    last_processed_version = ""
    if isinstance(state.get("last_processed_game_version"), str):
        last_processed_version = normalize_version(state["last_processed_game_version"])

    latest_report_version = read_version_from_latest_report(report_dir)
    old_ref_version = read_version_from_ref(old_ref)
    if old_ref.upper() == "HEAD":
        old_ref_version = old_ref_version or last_processed_version or latest_report_version

    baseline_version = last_processed_version or latest_report_version or old_ref_version

    print("== STS2 Update Check ==")
    print(f"Current extraction version: {current_version or 'unknown'}")
    print(f"Last processed version:     {last_processed_version or 'unknown'}")
    print(f"Latest report version:      {latest_report_version or 'unknown'}")
    print(f"{old_ref} inferred version:      {old_ref_version or 'unknown'}")
    if (
        current_version
        and baseline_version
        and current_version == baseline_version
        and not args.force
    ):
        print("\n[skip] No game version update detected. Use --force to run anyway.")
        run_step(["git", "status", "--short"])
        return

    print("== STS2 Update Pipeline ==")
    run_step(["python3", "tools/parsers/parse_all.py"])

    if not args.skip_images:
        run_step(["python3", "tools/copy_images.py"])

    if not args.skip_images and not args.skip_compress:
        run_step(
            [
                "python3",
                "tools/compress_images.py",
                "--root",
                "public/images",
                "--max",
                str(args.compress_max),
                "--quality",
                str(args.quality),
                "--png-colors",
                str(args.png_colors),
            ]
        )

    if not args.no_diff:
        diff_cmd = [
            "python3",
            "tools/diff_data.py",
            old_ref,
            "--record",
            "--out-dir",
            args.out_dir,
        ]
        if current_version:
            diff_cmd.extend(["--game-version", current_version])
        if args.report_name:
            diff_cmd.extend(["--report-name", args.report_name])
        print(f"\nAuto old ref: {old_ref}")
        run_step(diff_cmd)

    if current_version:
        save_state(
            STATE_FILE,
            {
                "last_processed_game_version": current_version,
            },
        )
        print(f"\nSaved update state -> {STATE_FILE}")

    run_step(["git", "status", "--short"])
    print("\nDone.")


if __name__ == "__main__":
    main()
