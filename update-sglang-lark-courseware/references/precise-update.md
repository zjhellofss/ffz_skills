# Precise Feishu Section Update

Use this workflow only after the user has explicitly requested a document write. By default, replace the named section in place. Correct source errors, improve expression, convert existing content into tables or Mermaid diagrams, and add necessary teaching structure inside that section. Do not append new substantive knowledge or change content outside the target boundary unless the user explicitly requests it.

## Contents

1. Read the target
2. Capture the deletion range
3. Write the replacement
4. Delete old blocks
5. Verify
6. Common failure modes

## 1. Read the target

Always read the current `lark-doc` skill and its required references first.

```bash
lark-cli docs +fetch \
  --doc "$DOC_URL" \
  --scope outline \
  --detail with-ids \
  --as user
```

Fetch the section after resolving its heading ID:

```bash
lark-cli docs +fetch \
  --doc "$DOC_URL" \
  --scope section \
  --start-block-id "$SECTION_HEADING_ID" \
  --detail with-ids \
  --as user
```

The section fetch normally ends before the next heading of the same or higher level. Record that next heading from the outline as an explicit safety boundary.

## 2. Capture the deletion range

Save or pipe the pre-write JSON response through:

```bash
python3 scripts/extract_section_block_ids.py \
  --start-id "$SECTION_HEADING_ID" \
  --end-id "$NEXT_SECTION_HEADING_ID" \
  --format csv
```

The script excludes both boundary headings and includes IDs nested inside lists and tables. Inspect the output before deletion. Resource blocks such as images and whiteboards are included when they have IDs.

If the section response does not include the end heading, fetch a range or a parent section that contains both boundaries.

## 3. Write the replacement

Create the XML payload with `apply_patch`, then replace only the old heading:

```bash
lark-cli docs +update \
  --doc "$DOC_URL" \
  --command block_replace \
  --block-id "$SECTION_HEADING_ID" \
  --content @replacement.xml \
  --as user
```

The payload must begin with the new heading. It may contain paragraphs, tables, callouts, code blocks, equations, and Mermaid whiteboards.

Use those components to re-express and organize the authorized content. Internal headings, stage labels, transitions, summaries, tables, Mermaid diagrams, and source corrections are allowed. Do not introduce new substantive examples, claims, benchmarks, or implementation details unless the user explicitly asks for supplementation or expansion.

## 4. Delete old blocks

Use the IDs captured before replacement:

```bash
lark-cli docs +update \
  --doc "$DOC_URL" \
  --command block_delete \
  --block-id "$OLD_BLOCK_IDS" \
  --as user
```

Do not include the old heading ID; `block_replace` already invalidated it. Do not include the next-section heading ID.

This deletion is permitted only to remove the superseded blocks inside the section being replaced. Never extend the deletion range into adjacent or unrelated content without explicit user authorization.

For an insertion that does not replace existing material, prefer `block_insert_after` on the last verified block immediately before the intended insertion point.

## 5. Verify

Re-fetch the outline and replacement section.

Check:

- heading uniqueness and order;
- next-section survival;
- new tables and whiteboards;
- expected code identifiers and terminology;
- absence of the old heading text and known obsolete claims;
- revision ID advancement.

Use keyword fetches for targeted checks, but use an outline or section fetch to verify structural boundaries.

## 6. Common failure modes

### Duplicate section

Cause: replacing the heading while leaving old sibling blocks.

Fix: delete the pre-recorded old content IDs, then fetch the section again.

### `result: failed` with no changes

Cause: stale ID, already deleted block, identical content, or malformed instruction.

Fix: fetch live IDs and retry only after confirming the target still exists.

### Accidentally broad edit

Cause: using `overwrite`, appending a second section, or deleting through the next heading.

Fix: restore from document history if necessary; then use exact section boundaries.

### Incorrect source ownership

Cause: attributing Worker-side Top-K, path scoring, or cache management to the model module, or treating every draft hidden state as a fresh target hidden state.

Fix: trace assignments across the model forward, Worker, Verify result, and `draft_extend` before writing.
