# Split Materialized Lark Markdown

Apply the installed `$organize-split-markdown` semantic segmentation rules to `source.md`, with these additions. Numbered files are reader-facing segments, so preserve source-authored content and meaningful rich previews, but omit export scaffolding that was added only for traceability.

## Boundary Rules

- Keep an image, whiteboard preview, attachment link, native table, or embedded-data preview with the nearest prose that introduces or explains it.
- Do not split inside a Markdown table, HTML table, HTML `<details>` block, HTML comment, code fence, or rich-content preview.
- Treat an embedded-data inline preview as one semantic block.
- Preserve every source-authored visible block and meaningful rich-content preview exactly once and preserve order.
- Do not preserve export-only scaffolding in numbered files by default:
  - Generic wrapper headings such as `### 嵌入电子表格：<token-or-sheet-id>` or `### 嵌入多维表格：<token-or-table-id>`
  - Complete snapshot links such as `[查看完整快照](embedded/...)`
  - Adjacent provenance comments such as `<!-- lark-resource: ... -->`
- Preserve a wrapper heading only when it is a real user-authored caption/title needed to understand the following table.

## Relative Paths

`source.md` lives one level above `split/`. Adjust retained local links mechanically while writing numbered files:

| In `source.md` | In `split/*.md` |
|---|---|
| `assets/...` | `../assets/...` |
| `embedded/...` | `../embedded/...` |

Path adjustment for retained links and export-scaffolding removal are the only content-level differences allowed between a materialized source block and its split copy.

## Index

Generate `split/index.md` with:

- Numbered file list
- Topic and length for each file
- Logical relationship to adjacent files
- Rich-content references contained in each file
- Any intentionally large or small segment and the reason

Do not use the index to reintroduce hidden export scaffolding into every segment. If provenance is needed, point to `manifest.md` or the local snapshot under `embedded/`.
