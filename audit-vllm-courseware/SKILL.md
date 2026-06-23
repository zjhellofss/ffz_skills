---
name: audit-vllm-courseware
description: Audit a vLLM technical lesson against the locally installed vLLM source tree and produce a staleness report. Use when the user provides vLLM courseware and wants to know which content may be outdated, which conflicts with the current source implementation, and which needs further verification — without rewriting the full text. Use instead of review-vllm-courseware when a diagnostic report is wanted rather than a revised version.
---

# Audit vLLM Courseware

## Purpose

Given a vLLM technical lesson, check it against the locally installed/cloned vLLM source code and produce a diagnostic report that classifies content into:

1. **Outdated** — references removed/renamed modules, classes, functions, configs, parameters, defaults, or behaviors no longer present in the installed source.
2. **Inconsistent** — contradicts the current source implementation (different semantics, signatures, defaults, control flow, or file layout), even if the referenced symbol still exists.
3. **Needs Verification** — cannot be confirmed from the local source within a reasonable effort. Do not rely on memory; list the claim and state what was checked.

Rewriting the full lesson is out of scope. Output is a report, not a revised document.

## Workflow

1. Locate the installed vLLM source tree. Use `python3 -c "import vllm, os; print(os.path.dirname(vllm.__file__))"`; fall back to `python` only when `python3` is unavailable. When the import fails, ask the user for the clone path before proceeding.
2. Record the installed version (`python3 -c "import vllm; print(vllm.__version__)"`) and the source path; include both in the report header.
3. Read the provided lesson text and extract every concrete, verifiable claim: module/class/function names, parameter names and defaults, command-line flags, config keys, file paths, version-sensitive behavior, control flow, and API surfaces.
4. For each claim, verify against the local source using `rg`, file reads, and `python3` introspection. Prefer the installed tree over imported runtime signal when the two disagree (write/discussion can lag source); note the discrepancy in the report.
5. Classify each checked claim into one of the three categories. Skip claims that are correct and current — do not list them.
6. Cite evidence for every finding: specific files, class/function names, line numbers when practical, and a short supporting quote or description.
7. Comparison scope: the installed source tree. When a claim references a feature introduced after the installed version (or removed before it), classify as Outdated with the note that the installed version may differ from upstream HEAD.
8. Do not browse the web. If external knowledge is needed, mark the claim as Needs Verification and state what local check was attempted.
9. Phrase source-backed descriptions using the same wording discipline as `$review-vllm-courseware` requires for `## Revised Text`: clean technical statements, no rebuttal framing, no comparison against the original mistake, and no visible correction trail.

## What to Audit

Prioritize:

- removed, renamed, or restructured modules, classes, functions, or constants
- changed command-line flags, config keys, parameter names, defaults, or value ranges
- changed parameter semantics, control flow, or module responsibilities
- API surfaces whose names, signatures, or response shapes changed
- version-sensitive behavior the lesson states unconditionally
- file paths or project layout that no longer matches the installed tree
- named integrations/connectors/backends that were added, removed, or moved

Avoid:

- subjective stylistic or pedagogical critique
- expanding or rewriting the lesson
- listing every correct claim — the report is for problems and unknowns only
- rebuttals, comparison against the original, or review commentary inside the `现状` / `源码实际行为` fields
- negative or corrective framing in source-backed descriptions. As in `$review-vllm-courseware`, write positive technical statements that read as if they had always been written correctly.

## Output

Respond in Chinese. Use this structure:

Keep the report diagnostic, but apply the `$review-vllm-courseware` `## Revised Text` wording rules to each `现状` / `源码实际行为` field: state the corrected source behavior directly, put critique and evidence only in the finding structure, and avoid wording that points back to the original mistake.

```markdown
## 审计信息

- vLLM 版本：<installed version>
- 源码路径：<source path>

## 过时

- 过时项 1:
  - 原文：<short quote of the claim>
  - 现状：<what the installed source shows instead>
  - 证据：<file:line / class / function / quote>

## 与源码不一致

- 不一致项 1:
  - 原文：<short quote>
  - 源码实际行为：<what the source does>
  - 证据：<file:line / class / function / quote>

## 待核对

- 待核对项 1:
  - 原文：<short quote>
  - 已尝试：<what was checked and why it was inconclusive>
```

When a category has no entries, write `无。` under that heading. Do not include a revised version of the lesson.
