#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_CACHE_FILE = Path("tools/.cache/compress_images_md5.json")
DEFAULT_BASELINE_FILE = Path("tools/.cache/source_images_md5.json")
SKIP_RELATIVE_PREFIXES = ("monsters/sprites/",)


def iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            if "atlases" in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            if any(rel.startswith(prefix) for prefix in SKIP_RELATIVE_PREFIXES):
                continue
            yield path


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def resize_image(path: Path, max_size: int, quality: int, png_colors: int) -> tuple[bool, str]:
    try:
        with Image.open(path) as img:
            img = img.convert("RGBA") if img.mode in ("P", "LA") else img.convert(img.mode)
            orig_w, orig_h = img.size
            if orig_w <= max_size and orig_h <= max_size:
                needs_resize = False
            else:
                needs_resize = True

            if needs_resize:
                scale = min(max_size / orig_w, max_size / orig_h)
                new_w = max(1, int(orig_w * scale))
                new_h = max(1, int(orig_h * scale))
                resized = img.resize((new_w, new_h), Image.LANCZOS)
            else:
                new_w, new_h = orig_w, orig_h
                resized = img

            ext = path.suffix.lower()
            if ext in (".jpg", ".jpeg"):
                resized = resized.convert("RGB")
                resized.save(path, quality=quality, optimize=True, progressive=True)
            elif ext == ".webp":
                resized.save(path, quality=quality, method=6)
            else:
                if png_colors and png_colors > 0:
                    # Quantize PNG for smaller file size (Tinypng-like reduction)
                    if resized.mode in ("RGBA", "LA"):
                        quantized = resized.convert("RGBA").quantize(colors=png_colors, method=Image.FASTOCTREE)
                    else:
                        quantized = resized.convert("RGB").quantize(colors=png_colors, method=Image.MEDIANCUT)
                    quantized.save(path, optimize=True)
                else:
                    # Preserve original colors (lossless)
                    resized.save(path, optimize=True)

            info = (
                f"{orig_w}x{orig_h} -> {new_w}x{new_h}"
                if needs_resize
                else f"{orig_w}x{orig_h} -> {new_w}x{new_h} (quality)"
            )
            return True, info
    except Exception as exc:
        return False, f"error: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Resize images in-place to a max dimension.")
    parser.add_argument("--root", default="public/images", help="Root directory to scan.")
    parser.add_argument("--max", type=int, default=1024, help="Max width/height.")
    parser.add_argument("--quality", type=int, default=85, help="JPEG/WebP quality.")
    parser.add_argument("--png-colors", type=int, default=256, help="PNG palette size (0 to keep original colors).")
    parser.add_argument(
        "--cache-file",
        default=str(DEFAULT_CACHE_FILE),
        help="Md5 cache file path used to skip already-processed images.",
    )
    parser.add_argument(
        "--baseline-file",
        default=str(DEFAULT_BASELINE_FILE),
        help="Optional baseline md5 file; matching files are treated as already processed.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"root not found: {root}")
        return 1

    cache_path = Path(args.cache_file)
    cache = load_cache(cache_path)
    baseline_md5 = load_baseline_md5(Path(args.baseline_file))
    settings = {
        "root": str(root.resolve()),
        "max": int(args.max),
        "quality": int(args.quality),
        "png_colors": int(args.png_colors),
    }

    cache_files = cache.get("files", {}) if isinstance(cache.get("files"), dict) else {}
    settings_match = cache.get("settings") == settings

    changed = 0
    skipped = 0
    skipped_baseline = 0
    failed = 0
    total = 0
    new_cache_files: dict[str, str] = {}

    for path in iter_images(root):
        total += 1
        rel = path.relative_to(root).as_posix()
        before_md5 = file_md5(path)

        if settings_match and cache_files.get(rel) == before_md5:
            skipped += 1
            new_cache_files[rel] = before_md5
            continue

        baseline_hash = baseline_md5.get(rel)
        if baseline_hash and before_md5 == baseline_hash:
            skipped += 1
            skipped_baseline += 1
            new_cache_files[rel] = before_md5
            continue

        updated, info = resize_image(path, args.max, args.quality, args.png_colors)
        if updated:
            changed += 1
            print(f"resized: {path} ({info})")
            new_cache_files[rel] = file_md5(path)
        else:
            failed += 1
            print(f"failed: {path} ({info})")

    cache_payload = {
        "version": 1,
        "settings": settings,
        "baseline_file": str(Path(args.baseline_file)),
        "files": new_cache_files,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"done. scanned={total}, resized={changed}, skipped={skipped} "
        f"(baseline={skipped_baseline}), failed={failed}"
    )
    print(f"cache: {cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
