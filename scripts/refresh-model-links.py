#!/usr/bin/env python3
"""Create lightweight symlinks for Periscope's llama.cpp model router.

Never copies, moves, edits, or deletes original GGUF files.
Only uses the dedicated Periscope model catalogue.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

DEFAULT_SOURCES = [
    Path("/mnt/SmollSSD/Natural Stupidity/llamacpp/models"),
    Path("/mnt/SmollSSD/Custom models"),
    Path.home() / "Documents/Apps/Storyteller/models",
]


def sources() -> list[Path]:
    extra = os.environ.get("PERISCOPE_MODEL_SOURCES", "")
    paths = DEFAULT_SOURCES[:]
    paths.extend(Path(p).expanduser() for p in extra.split(os.pathsep) if p)
    return [p for p in dict.fromkeys(paths) if p.is_dir()]


def candidates(path: Path):
    # Known layout: model.gguf in the source root or inside an immediate child
    # directory (Jan, multi-file / multimodal, and custom models).
    for candidate in sorted(path.glob("*.gguf")) + sorted(path.glob("*/*.gguf")):
        if candidate.is_file() and not candidate.is_symlink():
            lower = str(candidate).lower()
            if candidate.name.lower().startswith("mmproj"):
                continue
            if "sentence-transformer" in lower or "embedding" in lower:
                continue
            yield candidate


def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._+\-]", "_", name)


def put_link(dst: Path, src: Path) -> bool:
    if dst.is_symlink():
        if dst.resolve() == src.resolve():
            return False
        print(f"SKIP (link already exists): {dst}", file=sys.stderr)
        return False
    if dst.exists():
        print(f"SKIP (path already exists): {dst}", file=sys.stderr)
        return False
    dst.symlink_to(src.resolve())
    return True


def refresh(catalog: Path, roots: list[Path]) -> int:
    catalog.mkdir(parents=True, exist_ok=True, mode=0o700)
    found = 0
    added = 0
    for source in roots:
        for model in candidates(source):
            found += 1
            # A multimodal model needs the projector in the same subdirectory.
            projectors = sorted(
                p for p in model.parent.glob("mmproj*.gguf")
                if p.is_file()
            )
            if projectors:
                subdir = catalog / safe_name(model.stem)
                if subdir.is_symlink() or (subdir.exists() and not subdir.is_dir()):
                    print(f"SKIP (folder conflict): {subdir}", file=sys.stderr)
                    continue
                subdir.mkdir(exist_ok=True)
                if put_link(subdir / model.name, model):
                    added += 1
                for projector in projectors:
                    put_link(subdir / projector.name, projector)
            else:
                # Collision-safe filenames: if another location contains the
                # same filename, do not overwrite either symlink.
                name = safe_name(model.name)
                dest = catalog / name
                if dest.is_symlink() and dest.resolve() != model.resolve():
                    dest = catalog / (safe_name(model.parent.name) + "-" + name)
                if put_link(dest, model):
                    added += 1
    print(f"Found {found} model GGUF(s) in {len(roots)} source directories.")
    print(f"Created {added} new model links in {catalog}.")
    print("Original model files have not been modified or copied.")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh symlinks to existing local GGUF models")
    parser.add_argument("--catalog", type=Path, default=Path(
        os.environ.get("PERISCOPE_MODEL_DIR", str(Path.home() / ".local/share/periscope/model-links"))
    ))
    args = parser.parse_args()
    roots = sources()
    if not roots:
        print("No source folders found. Add paths through PERISCOPE_MODEL_SOURCES.", file=sys.stderr)
        return 1
    if not refresh(args.catalog.expanduser(), roots):
        print("No eligible GGUF files found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
