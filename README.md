# ffz_skills

这个仓库完整保存当前 Codex 环境中可用的 skills。每个 skill 都位于独立的顶层目录中，并保留其 `SKILL.md`、`agents/`、`assets/`、`references/`、`scripts/`、`tests/` 等配套资源。

当前共收录 48 个 skills：

- 16 个用户级 Codex skills
- 5 个 Codex 内置 skills
- 27 个 Agents / Lark skills

## 用户级 Codex skills

- `audit-vllm-courseware`
- `caiwu-fenxi`
- `code-flow-mermaid`
- `compare-semiconductor-fundamentals`
- `courseware-editor`
- `extract-vllm-revised-text`
- `jibenmian-pingfen`
- `jibenmian-pingfen-local-data`
- `lark-create-interview-guide`
- `lark-extract-split-doc`
- `organize-split-markdown`
- `review-sglang-courseware`
- `review-vllm-courseware`
- `review-vllm-split-courseware`
- `revise-markdown-from-audit`
- `update-sglang-lark-courseware`

## Codex 内置 skills

- `imagegen`
- `openai-docs`
- `plugin-creator`
- `skill-creator`
- `skill-installer`

## Agents / Lark skills

- `lark-approval`
- `lark-apps`
- `lark-attendance`
- `lark-base`
- `lark-calendar`
- `lark-contact`
- `lark-doc`
- `lark-drive`
- `lark-event`
- `lark-im`
- `lark-mail`
- `lark-markdown`
- `lark-minutes`
- `lark-note`
- `lark-okr`
- `lark-openapi-explorer`
- `lark-shared`
- `lark-sheets`
- `lark-skill-maker`
- `lark-slides`
- `lark-task`
- `lark-vc`
- `lark-vc-agent`
- `lark-whiteboard`
- `lark-wiki`
- `lark-workflow-meeting-summary`
- `lark-workflow-standup-report`

## 同步说明

同步时保留技能的全部源文件和资源文件，只排除不属于源码的本地运行产物：

- `__pycache__/`
- `.pytest_cache/`
- `*.pyc`、`*.pyo`
- `.DS_Store`

部分技能依赖本机软件包、数据目录、命令行工具或飞书授权；仅复制 skill 文件并不会自动安装这些外部依赖。
