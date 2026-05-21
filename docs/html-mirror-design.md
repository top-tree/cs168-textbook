# CS168 HTML Mirror Design

## Goal

Create a local static mirror of `https://textbook.cs168.io/` that can be opened from `site/index.html`, keeps the original published HTML/CSS/JS/images, defaults to dark mode, and adds Chinese, English, and bilingual reading modes.

## Approach

Use the published HTML as the source of truth. A Python script crawls same-site textbook pages, downloads same-site assets, rewrites internal links to local relative paths, and injects a small local language layer into every mirrored HTML page.

This keeps the local project independent of any source-site build toolchain.

## Translation Model

Translations live in JSON under `translations/`. The first milestone translates `intro/intro.html` fully enough to judge style and terminology. Chinese technical terms include the original English term in parentheses where useful.

Untranslated pages remain usable. In Chinese mode they keep the English body with a short local notice, while navigation labels can still be translated.

## Generated Output

The generated mirror is written to `site/`. The main entry is `site/index.html`, and every downloaded page and resource is stored under the same path shape as the original site.

## Verification

Tests cover URL-to-file mapping, relative-link rewriting, local script injection, default dark/Chinese mode hooks, and sample translation data.
