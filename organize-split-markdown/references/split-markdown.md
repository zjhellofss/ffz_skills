# Stage 2: Split Markdown by Semantics

Act as a professional technical-document splitting assistant. Split the standardized Markdown document into semantically complete files for later processing by GPT, Codex, or similar models.

## Target Directory

Create `split/` under the source document's parent directory. Save all split results there.

## Core Invariant

Split by semantic boundaries. Do not split by fixed word count, line count, token count, or paragraph count.

Use the standardized intermediate file as input. Preserve its content and original order exactly. Only reorganize file boundaries.

## Split Criteria

### Single Topic

Keep one core topic in each file. Consider a new file when the document begins discussing a new topic.

### Semantic Completeness

Make each file as independent and understandable as possible. Do not separate strongly related content.

### Suitability for Model Processing

Avoid excessive context dependency, extensive cross-file references, and mixed topics.

### Preserve Original Logic

Prefer existing headings, subheadings, chapter boundaries, and content transitions. Do not reorder content.

## File Size Guidance

Aim for 800-1500 Chinese characters per file. Allow 500-2500 Chinese characters. Keep a naturally larger topic intact when needed. Do not force a split merely to satisfy length guidance.

## File Naming

Use:

```text
<sequence>_<topic>.md
```

For example:

```text
001_xxx.md
002_xxx.md
003_xxx.md
```

Generate the topic from the file's actual content. Keep it concise, clear, and no longer than 20 Chinese characters.

## Content Preservation

Preserve headings, body text, code blocks, tables, image references, links, mathematical formulas, and Markdown formatting.

Do not modify, delete, polish, summarize, or rewrite content.

## Index

Generate `split/index.md` with:

- File list
- Topic of each numbered file
- Length of each numbered file
- Logical relationships between files

Generated navigation metadata belongs only in `split/index.md`, not in numbered content files.

## Completion Report

Report split statistics after writing all files. Do not perform content modifications beyond splitting.
