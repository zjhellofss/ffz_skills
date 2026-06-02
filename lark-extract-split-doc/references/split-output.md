# Split Materialized Lark Markdown

Apply the installed `$organize-split-markdown` semantic segmentation rules to `source.md`, with these additions.

## Boundary Rules

- Keep an image, whiteboard preview, attachment link, native table, or embedded-data preview with the nearest prose that introduces or explains it.
- Do not split inside a Markdown table, HTML table, HTML `<details>` block, HTML comment, code fence, or rich-content preview.
- Treat a large embedded-data snapshot link plus its inline preview as one semantic block.
- Preserve every materialized block exactly once and preserve order.

## Relative Paths

`source.md` lives one level above `split/`. Adjust local links mechanically while writing numbered files:

| In `source.md` | In `split/*.md` |
|---|---|
| `assets/...` | `../assets/...` |
| `embedded/...` | `../embedded/...` |

This path adjustment is the only content-level difference allowed between a materialized source block and its split copy.

## Index

Generate `split/index.md` with:

- Numbered file list
- Topic and length for each file
- Logical relationship to adjacent files
- Rich-content references contained in each file
- Any intentionally large or small segment and the reason

