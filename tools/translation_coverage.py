#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from mirror_textbook import default_translation_paths, merge_translations

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def canonical_translation_key(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub("", text)
    return (
        SPACE_RE.sub(" ", text)
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .strip()
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Report translation coverage against a skeleton file.")
    parser.add_argument("--skeleton", default="translations/_skeleton.json")
    parser.add_argument("--translations", default="translations")
    args = parser.parse_args()

    skeleton = load_json(Path(args.skeleton))
    merged = merge_translations(default_translation_paths(Path(args.translations)))

    total_pages = 0
    translated_pages = 0
    total_blocks = 0
    translated_blocks = 0
    missing: list[tuple[str, int, int]] = []

    for page_key, page_data in sorted(skeleton.get("pages", {}).items()):
        total_pages += 1
        expected_blocks = page_data.get("blocks", [])
        translated_page = merged.get("pages", {}).get(page_key, {})
        translated_by_en = {
            canonical_translation_key(block.get("en", "")): block.get("zh_html", "")
            for block in translated_page.get("blocks", [])
            if block.get("zh_html")
        }
        page_total = len(expected_blocks)
        page_done = sum(
            1
            for block in expected_blocks
            if translated_by_en.get(canonical_translation_key(block.get("en", "")))
        )
        total_blocks += page_total
        translated_blocks += page_done
        if page_done == page_total and page_total:
            translated_pages += 1
        else:
            missing.append((page_key, page_done, page_total))

    print(f"pages: {translated_pages}/{total_pages}")
    print(f"blocks: {translated_blocks}/{total_blocks}")
    if missing:
        print("missing:")
        for page_key, done, total in missing:
            print(f"  {page_key}: {done}/{total}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
