---
name: revise-markdown-from-audit
description: Apply confirmed findings from an audit, staleness report, code review, or fact-check report to an extracted Markdown document. Use when Codex must preserve the original Markdown, create a separate revised Markdown copy, keep the source style and structure, and make only low-risk updates for findings classified as outdated, inconsistent, or otherwise confirmed.
---

# Revise Markdown From Audit

## Purpose

Update a Markdown document using a prior audit report without rewriting the article. The output is a new Markdown file that remains easy to diff against the original.
Also produce a machine-readable change list so later tools can sync the exact local edits back to a source document without re-parsing a diff.

## Inputs

Identify these artifacts before editing:

- Original Markdown file or extracted Markdown text.
- Audit/report text that names confirmed problems, affected claims, and evidence.
- Desired output path. If unspecified, write a sibling file with a suffix such as `_revised.md` or `_audit_revised.md`.
- Desired change-list path. If unspecified, write a sibling JSON file next to the revised Markdown, such as `_audit_revised.change_list.json`.

If the original Markdown is only in memory, write it to a working file first. Do not overwrite the original.

## Workflow

1. Preserve the baseline.
   - Copy the original Markdown to a new output file before editing.
   - Keep headings, paragraph order, examples, image links, citations, and surrounding prose unless a confirmed finding requires a local change.
   - Do not normalize formatting, reflow the whole file, or clean unrelated text.

2. Build a change list from the audit.
   - Edit only findings that are classified as confirmed, such as `过时`, `与源码不一致`, `Outdated`, `Inconsistent`, or equivalent.
   - Do not edit `待核对`, `Needs Verification`, or speculative findings unless the user explicitly asks.
   - Skip general style suggestions and broad rewrites.
   - For each confirmed finding, record a machine-usable change-list entry with:
     - `old_text`: the exact minimal original text intended for replacement.
     - `new_text`: the exact replacement text.
     - `finding_type`: the audit category, such as `与源码不一致` or `Outdated`.
     - `applied`: whether this finding was applied to the revised Markdown.
     - Local occurrence counts, at minimum `local_old_occurrences_before` and `local_new_occurrences_after`.
   - Prefer JSON for the change list. Markdown tables are acceptable only as a secondary human-readable summary.

3. Make minimal local edits.
   - Prefer replacing the smallest sentence, phrase, code comment, list item, or code snippet that contains the stale claim.
   - Choose an `old_text` span that is minimal but unique in the original Markdown whenever possible.
   - Keep the author's terminology and tone where possible.
   - Avoid carrying audit-report wording into the revised article. In courseware or explanatory text, do not overuse phrases like “current source code” / “current implementation” / `当前源码` / `当前实现`; prefer article-native wording such as “now”, “in practice”, “the implementation”, or “the code” unless the source-code contrast is essential.
   - When a claim is partly correct, preserve the correct part and qualify only the incorrect part.
   - When a code sample is wrong, make the smallest syntactic and semantic fix needed for the audited version.
   - When a file path or symbol moved, update the exact path or symbol and avoid changing nearby explanation unless it depends on the old name.

4. Keep uncertainty visible.
   - Do not silently invent source behavior beyond the audit evidence.
   - If a finding cannot be applied without broader context, leave the original text unchanged and mention it in the final summary.
   - If a finding is not applied, still include a change-list entry with `applied: false`; leave `old_text`/`new_text` empty only when no reliable replacement span can be identified, and explain why in `notes`.
   - If the audit contains conflicting guidance, prefer the more specific, source-cited finding and report the conflict.

5. Validate the revised file.
   - Validate every change-list entry against local files:
     - Before editing, count `old_text` occurrences in the original Markdown.
     - After editing, count `new_text` occurrences in the revised Markdown.
     - When practical, confirm stale `old_text` no longer remains in the revised Markdown.
   - If `old_text` occurs 0 times or multiple times in the original, either expand the replacement span to make it unique or mark the entry `applied: false` and explain the ambiguity in `notes`.
   - Search the revised file for stale symbols, paths, or phrases named in confirmed findings.
   - Compare against the original with `diff -u` or equivalent and inspect that changes are limited to audited claims.
   - Count Markdown code fences before and after; the counts should match unless a confirmed edit intentionally adds or removes a fenced block.
   - If code snippets were edited, check obvious syntax issues in the edited snippet where practical.

## Change List Format

Create a JSON array like this:

```json
[
  {
    "id": "finding-001",
    "finding_type": "与源码不一致",
    "old_text": "exact original span",
    "new_text": "exact replacement span",
    "applied": true,
    "local_old_occurrences_before": 1,
    "local_old_occurrences_after": 0,
    "local_new_occurrences_after": 1,
    "notes": ""
  }
]
```

The `old_text` and `new_text` values should be directly usable by later `str_replace`-style sync tools. Do not store unified-diff markers, ellipses, or paraphrases in these fields.

## Output

Return:

- Path to the revised Markdown file.
- Path to the machine-readable change-list file.
- A short summary of the confirmed findings applied.
- Any confirmed findings not applied and why.
- Validation performed, including change-list occurrence counts, diff scope, and code fence count when relevant.

Do not include the full revised Markdown in the chat unless the user requests it.
