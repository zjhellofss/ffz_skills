---
name: review-sglang-courseware
description: Review and revise Chinese SGLang courseware against the source code of the locally installed SGLang Python package and the installed `$courseware-editor` skill. Use when the user provides SGLang lesson text, asks to verify factual accuracy, asks whether the content has important omissions, or requests corrected courseware text based on the locally installed SGLang package/source tree.
---

# Review SGLang Courseware

## Workflow

1. Apply the installed `$courseware-editor` skill before reviewing the lesson. If it is not already loaded in the current session, read `${CODEX_HOME:-$HOME/.codex}/skills/courseware-editor/SKILL.md` and any files it directly references that are needed for the requested output mode.
2. Treat the source tree of the SGLang library installed via Python as the primary technical authority for SGLang behavior. Use `python3` to locate the installed package path when needed, falling back to `python` only if `python3` is unavailable. Start with `import sglang` and inspect its package path; when the lesson discusses runtime, server, scheduler, model executor, tokenizer, constrained decoding, quantization, kernels, or related integrations, also inspect locally installed companion modules or packages that the source imports, such as SGLang runtime/server subpackages or local kernel packages when present.
3. Use tools such as `rg`, direct source inspection, and local documentation in that tree for verification. Prefer local source and local docs over memory.
4. Review only the courseware text provided by the user. Preserve its structure, tone, teaching rhythm, headings, and difficulty level unless a change is necessary for correctness or clarity.
5. Correct technical errors that conflict with the local source. When a judgment is supported by the source, cite specific files, classes, functions, or line references when practical.
6. Identify important omissions only when they would materially affect the lesson's accuracy or the learner's understanding. Do not expand the lesson merely to make it more comprehensive.
7. If a claim cannot be confirmed from the local source, do not rely on memory. List it in a separate `Unconfirmed in Source` section rather than mixing it into the main body.
8. Do not browse the web unless the user explicitly asks you to. If external knowledge conflicts with the local source, prefer the local source and state that clearly.

## Review Focus

Prioritize:

- incorrect or misleading explanations of how SGLang is designed, implemented, configured, executed, or exposed through its APIs and internal components
- version-sensitive behavior that should be verified against the installed source tree
- server/runtime behavior, request scheduling, batching, caching, tokenization, sampling, constrained decoding, model loading, distributed execution, and backend/kernel details when the lesson discusses them
- unclear explanations that may mislead learners
- missing prerequisites, constraints, caveats, or assumptions that are necessary for the specific lesson topic
- mismatches with the style or formatting rules required by the courseware-editor skill

Avoid:

- unrelated refactoring of the lesson
- broad background additions that are not necessary for the current topic
- changing examples, terminology, or ordering when the original content is already correct and clear

## Output

Respond in Chinese. Output only the findings, the unconfirmed-in-source items, and the revised text.

The `## Revised Text` section must be a clean, learner-facing final version of
the courseware. Do not include rebuttals, comparison against the original, or
review commentary in the revised text. Avoid phrasing such as "不是原文中的 X,
而是 Y", "原先理解不对", "应改为", "更准确地说", or any wording that points back
to the original mistake. Put all critique, uncertainty, and evidence only in
`## Findings` or `## Unconfirmed in Source`; the revised text should simply state
the corrected explanation.

In `## Revised Text`, do not mention review basis, source-verification context,
or evidence-source wording such as "当前源码", "本地源码", "当前配置", "源码中",
"根据源码", or "当前版本", unless that wording is part of the learner-facing
technical concept itself. Keep source references, file paths, line numbers, and
uncertainty only in `## Findings` or `## Unconfirmed in Source`.

Write corrections in the revised text as positive technical statements, not as
warnings about what the original text must not do. Avoid negative or corrective
framing such as "不能把它简化成...", "并不意味着...", "不要理解为...",
"并非所有场景...", "取决于..., 不能...", or "原文忽略了...". Prefer direct
conditions and mechanisms instead. The revised text should read as if it had
always been written correctly, with no visible correction trail.

Use this structure:

```markdown
## Findings

- Issue 1:
  - Original:
  - Problem:
  - Evidence:

- Required Additions:
  - Reason:
  - Suggested Location:

## Unconfirmed in Source

- Claim 1:
  - Original:
  - Note:

## Revised Text

<full revised courseware text, written as a clean final version without rebuttal
or review commentary>
```

If there are no clear errors, write:

```markdown
## Findings

No clear errors found.

## Unconfirmed in Source

None.

## Revised Text

<original text, or the full text with only necessary additions, written as a
clean final version without rebuttal or review commentary>
```

Omit the `Required Additions` item when no additions are needed.
