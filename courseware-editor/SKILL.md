---
name: courseware-editor
description: Refine, rewrite, and structure courseware content such as slide text, lecture notes, speaker scripts, teaching outlines, and technical explanations. Use when Codex needs to improve clarity, concision, flow, pedagogy, or wording for teaching materials, including trimming verbose explanations, making wording more natural, preserving technical correctness, or adapting the same content into slide-ready, lecture-ready, or handout-ready form.
---

# Courseware Editor

## Overview

Rewrite teaching materials so they read clearly, stay technically correct, and fit the target format. Default to preserving the author's meaning while improving structure, phrasing, and teaching value.

Read [references/output-modes.md](references/output-modes.md) when the user wants the same content rewritten for a specific teaching format.

## Workflow

1. Identify the target artifact.
   Determine whether the user wants slide text, lecture narration, handout prose, outline bullets, or light polishing of existing wording.
2. Preserve technical intent.
   Keep terminology, code identifiers, API names, equations, and causal relationships correct. Do not simplify away an important condition or mechanism.
3. Rewrite to fit the medium.
   Compress aggressively for slides, keep transitions natural for spoken narration, and expand definitions only when the material is for notes or handouts.
4. Improve structure before style.
   Reorder sentences when needed so ideas flow from context to mechanism to conclusion. Split overloaded sentences. Remove repetition.
5. Prefer teaching clarity.
   Make hidden subjects explicit, replace vague references, and state what each component does before discussing why it matters.

## Editing Rules

- Preserve the original claim unless the user asks for a conceptual rewrite.
- Prefer short, direct sentences over dense academic phrasing.
- Keep bilingual or mixed-language terminology when the surrounding material depends on it.
- Keep code, filenames, enum names, and protocol terms exactly as written unless the user asks to rename them.
- For slide text, favor one idea per line and remove filler transitions.
- For lecture narration, keep the wording conversational but not casual.
- For handout text, allow slightly more context so the paragraph can stand alone.
- If a statement seems technically wrong, flag it and offer a corrected version instead of silently changing meaning.

## Default Output Shapes

- If the user asks to "润色", return the revised text directly.
- If the user asks to "整理" or "重写", return a cleaned version with clearer structure.
- If the user asks to "简略一点" or "精简", shorten without changing meaning.
- If the user asks for "口语化", rewrite for spoken teaching delivery.
- If the requested format is unclear, provide one concise revision and briefly note the assumed format.

## Scope Notes

- Work from the text the user provides. Do not invent missing factual details unless the user asks for supplementation.
- When the material is technical, keep precision ahead of elegance.
- When the material is explanatory, optimize for what a student can understand on first read or first listen.
