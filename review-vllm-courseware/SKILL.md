---
name: review-vllm-courseware
description: Review and revise Chinese vLLM courseware against the local vLLM source tree and the installed $courseware-editor skill. Use when the user sends vLLM lesson text, asks to check factual accuracy, asks whether content has omissions, or asks for corrected courseware text based on /root/miniconda3/lib/python3.12/site-packages/vllm.
---

# Review vLLM Courseware

## Workflow

1. Apply the installed `$courseware-editor` skill before reviewing the lesson. If the skill is not already loaded in the current session, read `/root/.codex/skills/courseware-editor/SKILL.md` and any directly referenced files needed for the requested output mode.
2. Treat `/root/miniconda3/lib/python3.12/site-packages/vllm` as the primary technical authority for vLLM behavior. Use `rg`, source reads, and local docs in that tree as needed.
3. Check only the courseware text the user provides. Preserve its structure, tone, teaching rhythm, headings, and level unless a change is necessary for correctness or clarity.
4. Fix technical errors that conflict with the local source. For source-backed judgments, cite specific files, classes, functions, or line references when practical.
5. Look for important omissions only when the omission would materially hurt the lesson's accuracy or learner understanding. Do not expand merely to make the lesson more comprehensive.
6. If a claim cannot be confirmed from the local source, say `源码中未确认` instead of relying on memory.
7. Do not browse the web unless the user explicitly asks. If local source and external knowledge conflict, prefer the local source and say so.

## Review Focus

Prioritize:

- incorrect vLLM architecture, execution flow, scheduler/cache/worker/model-runner behavior, or API usage
- version-sensitive behavior that should be verified in the installed source tree
- unclear explanations that may mislead students
- missing prerequisites, constraints, or caveats that are necessary for the specific lesson topic
- mismatches between the courseware and the courseware-editor style or formatting rules

Avoid:

- unrelated refactors of the lesson
- broad background additions that are not needed for the current topic
- changing examples, terminology, or ordering when the original is already correct and clear

## Output

Respond in Chinese. Output only the findings and the revised text.

Use this structure:

```markdown
## 发现的问题

- 问题 1：
  - 原文：
  - 问题说明：
  - 依据：

- 必要补充：
  - 补充原因：
  - 建议补充位置：

## 修改后的文本

<完整的修改后课件文本>
```

If there are no clear errors, write:

```markdown
## 发现的问题

未发现明确错误。

## 修改后的文本

<原文，或只包含必要补充后的完整文本>
```

Omit the `必要补充` item when no supplement is needed.
