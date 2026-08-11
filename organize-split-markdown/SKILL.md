---
name: organize-split-markdown
description: "Process an existing Markdown document by splitting it into fine-grained, semantically complete segments and normalizing each segment before it is written, then generate an index. Use when Codex needs to handle long Markdown notes, courseware, transcripts, or technical documents in a segment-by-segment workflow without changing content."
---

# Organize and Split Markdown

Process one Markdown source document in a segment-by-segment workflow. Preserve the source file unless the user explicitly requests replacement. Prefer finer semantic cuts when a topic can still stand alone without losing meaning.

## Workflow

1. Identify the source Markdown file and its parent directory.
2. Read [split-markdown.md](references/split-markdown.md) and [format-markdown.md](references/format-markdown.md).
3. Create or inspect `split/` under the source file's parent directory before writing any numbered files.
4. Move through the source document by semantic boundary, one segment at a time, and cut more finely when adjacent content clearly shifts topic, subtopic, argument step, example group, or procedure step.
5. For each segment, normalize Markdown formatting only, then write the segment to its numbered file. Keep the segment content fixed; only Markdown structure and spacing may change.
6. Verify for each numbered file that no content was added, removed, rewritten, reordered, summarized, technically corrected, or merged with adjacent segments.
7. Generate `split/index.md` after all numbered files are written and report the split statistics.

## Output Layout

```text
<source-directory>/
|-- <source-name>.md
`-- split/
    |-- index.md
    |-- 001_<topic>.md
    |-- 002_<topic>.md
    `-- ...
```

## Validation

While processing each segment, confirm:

- The split is driven by semantic boundaries, not by fixed character count, line count, token count, or paragraph count.
- Each file covers one clearly bounded topic, subtopic, procedure step, or logically self-contained example cluster.
- When a section contains multiple independent subtopics, split them apart unless doing so would break meaning or leave either side dependent on the other.
- Prefer more files with cleaner semantic isolation over fewer files with mixed content.
- Every source passage appears exactly once across the numbered split files.
- Numbered files preserve the original order.
- No numbered file contains generated summaries or bridging text.
- Code fences are normalized clearly when content already exists in the source segment, but the code content itself is not changed.
- Lists, tables, quotes, headings, blank lines, and special characters are preserved in content and normalized only in Markdown syntax.
- Semantic boundaries are adjusted only to keep a passage intact or to separate distinct topics more cleanly; do not rewrite content to force a split. When in doubt, keep a smaller semantic unit intact rather than merging it into a broader adjacent block.
- `split/index.md` contains only generated navigation metadata: file list, topic, length, and logical relationships.
- Existing unrelated files are not overwritten silently. Inspect an existing `split/` directory before updating it.

## User-Facing Response

Keep the final response brief. Report the `split/` path, the number of split files, and any validation limitation.
