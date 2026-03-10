#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

from PIL import Image


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def iter_images(root: Path) -> Iterable[Path]:
	for path in root.rglob("*"):
		if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
			yield path


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
	args = parser.parse_args()

	root = Path(args.root)
	if not root.exists():
		print(f"root not found: {root}")
		return 1

	changed = 0
	total = 0
	for path in iter_images(root):
		total += 1
		updated, info = resize_image(path, args.max, args.quality, args.png_colors)
		if updated:
			changed += 1
			print(f"resized: {path} ({info})")

	print(f"done. scanned={total}, resized={changed}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
