"""Shared filesystem paths for parser scripts.

This keeps tools/parsers aligned with both repository layouts:
- current:   <repo>/tools/parsers
- backend:   <repo>/backend/app/parsers
"""

from pathlib import Path


def resolve_base(start_file: str) -> Path:
    start = Path(start_file).resolve()
    for parent in [start.parent, *start.parents]:
        if (parent / "extraction").is_dir() and (parent / "data").is_dir():
            return parent
    raise RuntimeError(
        f"Could not locate project root from {start}. "
        "Expected directories: extraction/ and data/."
    )


BASE = resolve_base(__file__)
DECOMPILED = BASE / "extraction" / "decompiled"
LOCALIZATION_EN = BASE / "extraction" / "raw" / "localization" / "eng"
LOCALIZATION_ZH = BASE / "extraction" / "raw" / "localization" / "zhs"
OUTPUT = BASE / "data"

_public_images = BASE / "public" / "images"
_legacy_images = BASE / "backend" / "static" / "images"
IMAGES_ROOT = _public_images if _public_images.exists() else _legacy_images
