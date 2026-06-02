---
name: lark-extract-split-doc
description: "Extract a Feishu/Lark docx or wiki document into a local Markdown package, preserve visible images, attachments, whiteboards, native tables, embedded Sheets, embedded Base tables, and referenced blocks with source metadata, then split the materialized Markdown into fine-grained semantic segments. Use when Codex needs to download and segment a Feishu/Lark document URL or token without losing rich document content in the split files."
---

# Extract and Split Lark Documents

Extract a Feishu/Lark document into a local, inspectable package before splitting it. Keep the remote document read-only. Make rich content visible in the exported Markdown and in every numbered segment that contains it.

## Required Skills

Read these installed skills before executing:

1. `$HOME/.agents/skills/lark-shared/SKILL.md`
2. `$HOME/.agents/skills/lark-doc/SKILL.md`
3. `$HOME/.agents/skills/lark-doc/references/lark-doc-fetch.md`
4. `${CODEX_HOME:-$HOME/.codex}/skills/organize-split-markdown/SKILL.md`
5. `${CODEX_HOME:-$HOME/.codex}/skills/organize-split-markdown/references/split-markdown.md`
6. `${CODEX_HOME:-$HOME/.codex}/skills/organize-split-markdown/references/format-markdown.md`

Read [rich-content.md](references/rich-content.md) before materializing the export. Read the relevant installed `lark-sheets` or `lark-base` skill before extracting an embedded Sheet or Base table.

## Output Layout

Use an output directory chosen by the user. If none is given, create a concise document-named directory under the current working directory.

```text
<output-directory>/
|-- source.xml
|-- source.md
|-- manifest.md
|-- assets/
|-- embedded/
`-- split/
    |-- index.md
    |-- 001_<topic>.md
    |-- 002_<topic>.md
    `-- ...
```

Inspect an existing output directory before writing. Do not overwrite unrelated files silently. Add a suffix or ask before replacing prior exports.

## Workflow

1. Fetch the whole source document as XML:

   ```bash
   lark-cli docs +fetch --api-version v2 --doc "<URL-or-token>" --doc-format xml --detail full
   ```

2. Save the returned document content exactly as `source.xml`. Treat this as the immutable extraction record.
3. Materialize `source.md` from the XML by preserving text order and applying [rich-content.md](references/rich-content.md). Download assets into `assets/`; write expanded embedded-data snapshots into `embedded/`.
4. Write `manifest.md` with the source URL or token, document ID, revision ID, extraction time, downloaded assets, expanded resources, commands used, and any limitations. Never include access tokens or secrets.
5. Split `source.md` using the installed `$organize-split-markdown` workflow and [split-output.md](references/split-output.md).
6. Verify that every visible text passage and rich-content block from `source.md` appears exactly once across numbered files, in original order.
7. Report the output path, segment count, extracted asset count, expanded embedded-resource count, and limitations.

## Preservation Rules

- Preserve remote source fidelity in `source.xml`; do not rewrite it.
- Keep `source.md` readable without requiring the reader to infer the meaning of a raw token.
- Keep each image, table, attachment, whiteboard preview, and expanded embedded-data block adjacent to the prose that introduced it.
- Keep source metadata in a nearby HTML comment or a concise visible source link.
- Prefer local relative links so the package remains usable after moving it.
- Preserve unsupported blocks as visible placeholders with their type and source metadata. Never silently drop them.
- Do not modify the remote Feishu/Lark document.

## Validation

Confirm:

- `source.xml`, `source.md`, and `manifest.md` exist.
- Every downloaded local link resolves.
- Each data-bearing embedded Sheet or Base block has a visible snapshot or a visible linked snapshot.
- Native tables remain rendered tables, not flattened prose.
- Numbered files preserve semantic boundaries and source order.
- Asset and embedded snapshot links in `split/*.md` use paths relative to `split/`.
- No numbered file contains generated summaries or bridging prose.

