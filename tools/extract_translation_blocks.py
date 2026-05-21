#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path


TRANSLATABLE_TAGS = {"h1", "h2", "h3", "p", "li"}
SKIP_TAGS = {"script", "style", "nav", "footer"}


class ContentBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.in_content = False
        self.content_depth = 0
        self.skip_depth = 0
        self.capture_tag: str | None = None
        self.capture_depth = 0
        self.html_parts: list[str] = []
        self.text_parts: list[str] = []
        self.blocks: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        classes = attr_map.get("class", "").split()
        if not self.in_content and ("content" in classes or "main-content" in classes):
            self.in_content = True
            self.content_depth = 1
            return

        if not self.in_content:
            return

        self.content_depth += 1
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if self.capture_tag:
            self.capture_depth += 1
            self.html_parts.append(self.get_starttag_text())
        elif tag in TRANSLATABLE_TAGS:
            self.capture_tag = tag
            self.capture_depth = 1
            self.html_parts = []
            self.text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if not self.in_content:
            return

        if self.skip_depth:
            if tag in SKIP_TAGS:
                self.skip_depth -= 1
            self.content_depth -= 1
            if self.content_depth <= 0:
                self.in_content = False
            return

        if self.capture_tag:
            self.capture_depth -= 1
            if self.capture_depth == 0:
                text = normalize_text("".join(self.text_parts))
                html = normalize_html("".join(self.html_parts))
                if text and not text.startswith("Table of contents"):
                    self.blocks.append({"en": text, "en_html": html, "zh_html": ""})
                self.capture_tag = None
                self.html_parts = []
                self.text_parts = []
            else:
                self.html_parts.append(f"</{tag}>")

        self.content_depth -= 1
        if self.content_depth <= 0:
            self.in_content = False

    def handle_data(self, data: str) -> None:
        if self.capture_tag and not self.skip_depth:
            self.html_parts.append(data)
            self.text_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.capture_tag and not self.skip_depth:
            value = f"&{name};"
            self.html_parts.append(value)
            self.text_parts.append(value)

    def handle_charref(self, name: str) -> None:
        if self.capture_tag and not self.skip_depth:
            value = f"&#{name};"
            self.html_parts.append(value)
            self.text_parts.append(value)


def normalize_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(value.split())


def normalize_html(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def page_key(path: Path, site_dir: Path) -> str:
    rel = path.relative_to(site_dir).as_posix()
    if rel == "index.html":
        return "/"
    return "/" + rel


def extract_page(path: Path, site_dir: Path) -> dict[str, object]:
    parser = ContentBlockParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return {"title": path.stem, "blocks": parser.blocks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract translatable blocks from mirrored HTML.")
    parser.add_argument("--site", default="site")
    parser.add_argument("--output", default="translations/_skeleton.json")
    args = parser.parse_args()

    site_dir = Path(args.site)
    pages = {}
    for html in sorted(site_dir.rglob("*.html")):
        if "cs168-local" in html.parts:
            continue
        extracted = extract_page(html, site_dir)
        if extracted["blocks"]:
            pages[page_key(html, site_dir)] = extracted

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"nav_titles": {}, "pages": pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {sum(len(page['blocks']) for page in pages.values())} blocks from {len(pages)} pages to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
