---
name: update-sglang-lark-courseware
description: Review Chinese SGLang technical courseware against the locally installed SGLang source, correct source-level errors, improve teaching clarity, restructure existing content with tables or Mermaid diagrams, and precisely replace only the requested section in an existing Feishu/Lark Docx or Wiki document. Use when a user supplies SGLang lesson text plus a Feishu document URL and asks to update, replace, polish, beautify, correct, explain, or supplement a named chapter or subsection. Default to in-place replacement; allow necessary teaching structure inside the section, but do not add new substantive knowledge or destructively change unrelated material unless the user explicitly requests it.
---

# Update SGLang Lark Courseware

## Required skills

Before acting:

1. Read and apply `courseware-editor`.
2. Read and apply `review-sglang-courseware`; treat the installed SGLang source tree as the technical authority.
3. Read and apply `lark-doc` through `lark-cli skills read lark-doc`, including every reference it requires for fetching and precise XML updates.
4. Read and apply `code-flow-mermaid` when the material contains a process, call chain, tree, lifecycle, or multi-stage data flow that benefits from a diagram.

If any required skill is unavailable, state the limitation and continue with the safest applicable workflow.

## Default authorization boundary

- Default to **in-place replacement** of the exact section named by the user.
- Rewrite, reorder, and format the material the user supplied or the material already present in the target section.
- Treat “润色”“整理”“美化”“更新对应内容” as authorization to correct source errors, optimize expression, improve teaching flow, and add necessary internal teaching structure without expanding the section's subject matter.
- Freely convert existing mappings, comparisons, flows, trees, and lifecycles into tables or Mermaid diagrams when this improves readability.
- Freely add structural headings, short transitions, labels, summaries, and callouts that organize existing information without introducing new substantive claims.
- Add explanations, examples, implementation details, or broader background when the user explicitly asks to supplement, expand, explain, illustrate, or add them.
- Do not add unrelated knowledge points, unsupported claims, new benchmark conclusions, or new subject areas without explicit authorization.
- Do not delete, overwrite, move, or rewrite adjacent sections, unrelated paragraphs, existing images, attachments, tables, or user edits unless the user explicitly identifies them as part of the requested change.
- Deleting the old blocks strictly inside the target section is allowed only as the mechanical completion of an explicitly requested in-place replacement.
- When the requested scope or permission is ambiguous, stop before writing and provide a proposed revision or ask for confirmation.

## Allowed transformations

The following operations are authorized inside the exact target section:

- ✅ Correct statements that conflict with the installed SGLang source.
- ✅ Optimize wording, ordering, terminology, and teaching rhythm.
- ✅ Convert existing content into tables, Mermaid diagrams, code blocks, or callouts.
- ✅ Add explanations that the user explicitly requests.
- ✅ Add necessary teaching structure such as internal headings, stage labels, short transitions, and concise takeaways.

Keep these transformations within the supplied topic and target-section boundary.

## Core workflow

### 1. Lock the edit scope

- Extract the exact requested heading, such as `3.2.3`.
- Confirm that the requested action is a replacement. If the user only asks for review, diagnosis, or suggestions, do not write to Feishu.
- Treat “只替换” as a hard boundary: preserve its parent introduction, previous sibling, next sibling, images, and all later chapters.
- Prefer a targeted section replacement over append, overwrite, or broad text replacement.
- Announce the intended boundary before writing.

### 2. Inspect the live document

- Fetch the outline with block IDs.
- Resolve Wiki URLs to the underlying Docx automatically through `lark-cli`.
- Fetch the target section with IDs and identify the next same-or-higher-level heading as the end boundary.
- Record the original target heading ID, next-section heading ID, and all old block IDs between them before the first write.

Read [references/precise-update.md](references/precise-update.md) for command patterns, block lifecycle rules, and verification checks.

### 3. Verify the technical content

- Locate the installed package and inspect the implementation with `rg` and focused source reads.
- Verify every version-sensitive claim: classes, functions, configuration names, routing order, tensor ownership, cache semantics, default values, and implementation constraints.
- Distinguish paper-level claims from SGLang runtime behavior.
- Do not present unverified paper dates, benchmark numbers, or algorithm properties as source-confirmed facts.
- Correct misleading ownership boundaries. For example, distinguish target hidden states synchronized by `draft_extend` from hidden states produced during subsequent draft steps.

### 4. Rewrite for teaching clarity

Preserve the subject boundary of the supplied material by default. Source inspection authorizes correcting factual errors and removing misleading claims. Add broader background, extra examples, benchmarks, or implementation details only when the user explicitly requests them.

Organize material in this order when applicable:

1. concept or purpose;
2. runtime mechanism;
3. source-aligned code excerpt;
4. variable or field table;
5. numeric example;
6. caveat or boundary;
7. concise takeaway.

Use:

- tables for repeated mappings and comparisons;
- callouts for one decisive distinction, invariant, or constraint;
- Mermaid for flows, trees, state transitions, and ownership boundaries;
- code blocks for code, tensor shapes, and compact sequences;
- short paragraphs with one teaching point each.

Use components proactively when they restate or organize existing material more clearly. Necessary internal headings, transitions, and summaries are teaching structure rather than substantive expansion. A component that introduces new factual content requires explicit user authorization.

Avoid decorative repetition, duplicated prose and diagrams, oversized headings, and screenshots when a native table or Mermaid diagram communicates the idea more clearly.

Preserve exact identifiers such as `EAGLEWorkerV2`, `draft_extend`, `speculative_num_draft_tokens`, and `TARGET_VERIFY`.

Use the document's established terminology. In this courseware, prefer “目标模型补充 Token” over “尾随 Token”; retain source identifiers such as `bonus_tokens` only inside code or when explicitly explaining the implementation name.

### 5. Build the replacement as Docx XML

- Use XML for precise edits.
- Create temporary XML with `apply_patch`, not shell redirection.
- Start the payload with the replacement heading at the same level as the original.
- Keep Mermaid labels short and apply consistent soft colors.
- Use tables with concise headers and avoid deeply nested lists.
- Validate risky XML characters such as `<`, `>`, and `&` before upload.

### 6. Replace, then remove the old sibling blocks

1. Replace the original heading block with the complete new section using `block_replace`.
2. Delete the previously recorded old content block IDs between the replaced heading and the next-section boundary.
3. Never delete the next-section heading.

Replacing a heading does not automatically remove its following sibling content. Do not leave the old section below the new one.

For long sections, use `scripts/extract_section_block_ids.py` on a pre-write `docs +fetch` JSON response to produce the deletion list.

### 7. Verify the live result

Fetch the outline and the new section again. Confirm:

- exactly one target heading exists;
- the next-section heading still exists and remains adjacent;
- requested functions, parameters, and terminology appear;
- superseded headings, claims, screenshots, and terminology are absent;
- Mermaid blocks were created without warnings;
- no old content remains after the replacement;
- only the requested section changed.

Treat a write response with `result: failed`, degradation warnings, or “no document changes” as unsuccessful until a fresh fetch proves otherwise.

### 8. Clean up and report

- Delete temporary XML files with `apply_patch`.
- Report the exact section updated, important source-aligned corrections, unchanged boundaries, final revision ID, and the document link.
- Keep the handoff concise; do not reproduce the entire inserted section unless requested.

## Safety rules

- Default to replacement, not append or supplementation.
- Correct source errors and add necessary teaching structure inside the target section without separate confirmation.
- Do not create new substantive knowledge, examples, benchmarks, or unrelated explanations without an explicit request.
- Do not perform destructive changes outside the exact target section without an explicit request.
- Never use whole-document `overwrite` for a subsection request.
- Never infer permission to rewrite adjacent sections.
- Capture old block IDs before replacing their heading.
- Do not reuse invalidated block IDs after replacement except for independently recorded sibling blocks whose lifecycle remains valid.
- Preserve unrelated user content, images, and existing edits.
- Verify with a live fetch rather than trusting only the write response.
