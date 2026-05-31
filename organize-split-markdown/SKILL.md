---
name: organize-split-markdown
description: "Standardize an existing Markdown document without changing its content, then split the standardized document into semantically complete Markdown files with an index. Use when Codex needs to process long Markdown notes, courseware, transcripts, or technical documents in two strict stages: format normalization first, semantic splitting second."
---

# Organize and Split Markdown

Process one Markdown source document in two stages. Preserve the source file unless the user explicitly requests replacement.

## Workflow

1. Identify the source Markdown file and its parent directory.
2. Read [format-markdown.md](references/format-markdown.md).
3. Normalize Markdown formatting only. Write the result to `<source-stem>.formatted.md` beside the source file.
4. Verify that no content was added, removed, rewritten, reordered, summarized, or technically corrected. Fix the formatted file if this invariant is violated.
5. Read [split-markdown.md](references/split-markdown.md).
6. Split `<source-stem>.formatted.md` by semantic boundaries. Create or update `split/` under the source file's parent directory.
7. Generate `split/index.md` and report the split statistics.

Complete stage 1 before starting stage 2. Use the formatted intermediate file as the only input to stage 2.

## Output Layout

```text
<source-directory>/
|-- <source-name>.md
|-- <source-stem>.formatted.md
`-- split/
    |-- index.md
    |-- 001_<topic>.md
    |-- 002_<topic>.md
    `-- ...
```

## Validation

After formatting, compare the source and formatted intermediate conceptually: only Markdown syntax normalization and blank-line normalization may differ.

After splitting, confirm:

- Every source passage from the formatted intermediate appears exactly once across the numbered split files.
- Numbered files preserve the original order.
- No numbered file contains generated summaries or bridging text.
- `split/index.md` contains only generated navigation metadata: file list, topic, length, and logical relationships.
- Existing unrelated files are not overwritten silently. Inspect an existing `split/` directory before updating it.

## User-Facing Response

Keep the final response brief. Report the formatted intermediate path, the `split/` path, the number of split files, and any validation limitation.
