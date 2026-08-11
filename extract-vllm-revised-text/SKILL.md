---
name: extract-vllm-revised-text
description: Extract the `## Revised Text` section from every independently reviewed Markdown file produced after `$review-vllm-split-courseware`, then write same-named standalone Markdown files to a separate output directory. Use when Codex needs to organize reviewed vLLM courseware into clean final segments without findings or unconfirmed-source notes.
---

# Extract vLLM Revised Text

Convert the reviewed output from `$review-vllm-split-courseware` into standalone courseware segments. Process files independently and preserve filenames.

## Workflow

1. Identify the input directory. Default to `./reviewed`.
2. Identify the output directory. Default to `output/` beside the input directory.
3. Enumerate `*.md` files in the input directory, sorted by filename. Include `index.md` when present.
4. Process exactly one file at a time:
   - Extract the content below the exact second-level heading `## Revised Text`.
   - Stop before the next second-level heading, if any.
   - Remove surrounding blank lines.
   - Write the extracted content to the same filename under the output directory.
5. Report each file status and the total, success, and failure counts.

## Deterministic Runner

Use [scripts/extract_revised_text.sh](scripts/extract_revised_text.sh):

```bash
scripts/extract_revised_text.sh [input-directory] [output-directory]
```

The defaults are `./reviewed` and `<input-parent>/output`.

## Constraints

- Never merge multiple Markdown files.
- Never overwrite reviewed input files.
- Preserve filenames; change only the directory.
- Treat a missing or empty `## Revised Text` section as a per-file failure.
- Continue processing remaining files after a per-file failure.
- Write only the revised courseware body to each output file. Do not retain the `## Revised Text` wrapper heading.
- Do not browse the web. This task is a local structural extraction and requires no content review.

## User-Facing Response

Keep the final response concise. Report the output directory, each file status, and:

```text
Total: <count>
Success: <count>
Failed: <count>
```
