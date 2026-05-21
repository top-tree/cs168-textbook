# CS168 Local Bilingual Textbook Site Design

## Goal

Build a local static version of `https://textbook.cs168.io/` that preserves the original site's layout, navigation, images, theme, and page structure while adding Chinese translation support.

The first implementation will provide the complete multilingual framework and one fully translated sample chapter, `Introduction / Introduction to the Internet`. If the sample quality is acceptable, the same content structure can be extended to the rest of the textbook.

## Source And License

Use the upstream source repository `berkeley-cs168/textbook`, which is the source for the published CS168 textbook and is built with GitHub Pages/Jekyll using the Just the Docs theme.

The upstream textbook is licensed under Creative Commons Attribution-ShareAlike 4.0 International. The local derivative must preserve attribution and license information from the original site.

## Architecture

Use the upstream Jekyll project as the base instead of scraping published HTML. This keeps the original theme, include files, Sass, navigation, page front matter, assets, and internal links intact.

Add a small multilingual enhancement layer:

- A language switcher in the existing page chrome.
- A default Chinese view.
- A pure English view that renders original content without translation.
- A bilingual view that renders English first and Chinese translation below.
- A persisted language preference in local storage.
- A default dark-mode preference that matches the original site's dark mode behavior.

The enhancement should be additive. It must not replace the Just the Docs theme, rebuild the visual design, or rewrite image paths.

## Content Model

For translated pages, keep the original English Markdown as the canonical content source and add Chinese translation in a structured way that can be rendered differently by mode.

For the sample chapter, translate `Introduction / Introduction to the Internet` manually enough to be readable and technically precise. Chinese technical terms should include the original English term in parentheses at first use or where clarity matters, such as `互联网(Internet)` or `分组交换(packet switching)`.

For untranslated pages in the first milestone:

- Chinese mode may show the original English content with a clear local-only fallback marker.
- English mode always shows the original page.
- Bilingual mode shows English and any available Chinese translation; pages without translation remain usable.

## Static Entry

Provide a local static entry point that can be opened from one HTML file. If Jekyll's generated asset paths require an HTTP server for reliable navigation, also provide a simple local server command and document it.

## Error Handling

If a page has no Chinese translation yet, the page should still render and navigation should still work. Missing translations must not break images, links, search, or theme scripts.

If JavaScript is disabled, the site should still show readable original content.

## Testing

Verify:

- The Jekyll site builds locally.
- The generated site can be opened locally.
- The language switcher changes between Chinese, English, and bilingual modes.
- Chinese is the default mode on first load.
- Dark mode is the default on first load.
- The sample chapter preserves original page structure and images.
- Internal links and sidebar navigation remain usable.

## Out Of Scope For First Milestone

- Translating the entire textbook.
- Rebuilding the visual design.
- Replacing Just the Docs.
- Changing upstream diagrams or image assets.
- Adding a backend service.
