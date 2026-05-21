#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mirror_textbook import default_translation_paths, merge_translations


def main() -> int:
    parser = argparse.ArgumentParser(description="Build site/cs168-local/translations.js from translations/*.json.")
    parser.add_argument("--translations", default="translations")
    parser.add_argument("--output", default="site/cs168-local/translations.js")
    args = parser.parse_args()

    paths = default_translation_paths(Path(args.translations))
    merged = merge_translations(paths)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "window.CS168_TRANSLATIONS = "
        + json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(merged.get('pages', {}))} translated pages to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
