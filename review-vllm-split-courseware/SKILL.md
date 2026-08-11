---
name: review-vllm-split-courseware
description: Review every Markdown file in a split vLLM courseware directory as an independent task by applying $review-vllm-courseware, then write same-named reviewed files to a separate output directory and report per-file status. Use when Codex needs to optimize, fact-check, or polish a directory such as split/ without merging files, constructing cross-file context, or overwriting the source segments.
---

# Review Split vLLM Courseware

Process each Markdown segment independently. Use `$review-vllm-courseware` for the technical review and `$courseware-editor` behavior inherited by that skill.

## Workflow

1. Identify the input directory. Default to `split/` under the current courseware directory.
2. Identify the output directory. Default to `reviewed/` beside the input directory.
3. Enumerate `*.md` files in the input directory, sorted by filename. Include `index.md` when present.
4. Process exactly one file at a time:
   - Read only the current filename and current file content.
   - Apply `$review-vllm-courseware`.
   - Write the complete Markdown result to the same filename under the output directory.
   - Do not include other split files in the task context.
5. Continue until every file has succeeded or failed independently.
6. Verify that output filenames match input filenames, successful outputs are non-empty, and each reviewed file contains:
   - `## Findings`
   - `## Unconfirmed in Source`
   - `## Revised Text`
7. Report each file status and the total, success, and failure counts.

## Deterministic Runner

Prefer [scripts/review_split.sh](scripts/review_split.sh) when `codex` is available on `PATH`:

```bash
scripts/review_split.sh [input-directory] [output-directory]
```

The defaults are `./split` and `<input-parent>/reviewed`.

The runner invokes one independent `codex exec` task per Markdown file. It does not concatenate files. Logs are stored under `<output-directory>/.logs/`.

## Constraints

- Never merge multiple Markdown files into one review request.
- Never analyze relationships between split files during review.
- Never overwrite source segments.
- Preserve filenames; change only the directory.
- Treat each file failure independently so remaining files still run.
- Do not browse the web unless the user explicitly requests it. `$review-vllm-courseware` uses the locally installed vLLM source tree as the technical authority.

## User-Facing Response

Keep the final response concise. Report the output directory, each file status, and:

```text
Total: <count>
Success: <count>
Failed: <count>
```
