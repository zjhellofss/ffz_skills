---
name: review-vllm-courseware
description: Review and revise Chinese vLLM courseware against the source code of the locally installed vLLM Python package and the installed `$courseware-editor` skill. Use when the user provides vLLM lesson text, asks to verify factual accuracy, asks whether the content has important omissions, or requests corrected courseware text based on the locally installed vLLM Python package.
---

# Review vLLM Courseware

## Workflow

1. Apply the installed `$courseware-editor` skill before reviewing the lesson. If it is not already loaded in the current session, read `/root/.codex/skills/courseware-editor/SKILL.md` and any files it directly references that are needed for the requested output mode.
2. Treat the source tree of the vLLM library installed via Python as the primary technical authority for vLLM behavior. Use `python` to locate the installed package path when needed, and use tools such as `rg`, direct source inspection, and local documentation in that tree for verification.
3. Review only the courseware text provided by the user. Preserve its structure, tone, teaching rhythm, headings, and difficulty level unless a change is necessary for correctness or clarity.
4. Correct technical errors that conflict with the local source. When a judgment is supported by the source, cite specific files, classes, functions, or line references when practical.
5. Identify important omissions only when they would materially affect the lesson’s accuracy or the learner’s understanding. Do not expand the lesson merely to make it more comprehensive.
6. If a claim cannot be confirmed from the local source, do not rely on memory. List it in a separate `Unconfirmed in Source` section rather than mixing it into the main body.
7. Do not browse the web unless the user explicitly asks you to. If external knowledge conflicts with the local source, prefer the local source and state that clearly.

## Review Focus

Prioritize:

- incorrect or misleading explanations of how vLLM is designed, implemented, configured, executed, or exposed through its APIs and internal components
- version-sensitive behavior that should be verified against the installed source tree
- unclear explanations that may mislead learners
- missing prerequisites, constraints, caveats, or assumptions that are necessary for the specific lesson topic
- mismatches with the style or formatting rules required by the courseware-editor skill

Avoid:

- unrelated refactoring of the lesson
- broad background additions that are not necessary for the current topic
- changing examples, terminology, or ordering when the original content is already correct and clear

## Output

Respond in Chinese. Output only the findings, the unconfirmed-in-source items, and the revised text.

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

<full revised courseware text>
```

If there are no clear errors, write:

```markdown
## Findings

No clear errors found.

## Unconfirmed in Source

None.

## Revised Text

<original text, or the full text with only necessary additions>
```

Omit the `Required Additions` item when no additions are needed.