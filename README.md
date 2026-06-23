# ffz_skills

这个仓库保存一组 Codex skills，用于课件润色、vLLM 课件源码核查、审计报告生成，以及根据审计结果对 Markdown 文档做低风险修订。

## Skills

### `courseware-editor`

通用课件编辑 skill。

适用于课件润色、重写、精简、结构整理，或把同一份内容改写成幻灯片、讲稿、讲义、提纲等教学形态。它的重点是保留原始技术含义，同时改善表达清晰度、内容结构和教学节奏。

### `audit-vllm-courseware`

vLLM 课件诊断审计 skill。

适用于只需要审计报告、不需要重写全文的场景。它会把课件中的具体可核查声明与本地安装的 vLLM 源码进行对照，并把问题分类为：

- `过时`：引用了已删除、重命名或迁移的模块、类、函数、配置项、默认值、文件路径或行为。
- `与源码不一致`：课件描述与本地源码中的签名、语义、默认值、控制流或职责划分不一致。
- `待核对`：在合理范围内无法从本地源码确认的声明。

输出是一份中文审计报告，包含 vLLM 版本、源码路径、问题分类和源码证据，不输出修订后的完整课件。

### `review-vllm-courseware`

中文 vLLM 课件审阅与修订 skill。

适用于既要核查技术准确性，又要得到一份干净修订版课件的场景。它会先应用 `courseware-editor` 的课件编辑原则，再以本地安装的 vLLM Python 包源码为主要依据检查 vLLM 相关声明。

输出包含：

- `Findings`：已确认的问题与证据
- `Unconfirmed in Source`：无法从本地源码确认的内容
- `Revised Text`：面向学习者的最终修订文本

`Revised Text` 要求直接呈现正确说明，不保留审稿痕迹、反驳口吻或“原文应改为”这类对照式表达。

### `revise-markdown-from-audit`

基于审计报告修订 Markdown 的 skill。

适用于已有审计报告，并希望把其中确认的问题最小化应用到 Markdown 文档中的场景。它会保留原文结构，另存一份修订后的 Markdown，并生成机器可读的 JSON change list，记录每一处精确替换。

这个 skill 适合用于需要可追踪、可回放、便于后续同步回源文档的低风险修订流程。

## 推荐工作流

### 只诊断 vLLM 课件问题

使用 `audit-vllm-courseware`。它只输出过时、不一致和待核对项，不重写全文。

### 生成修订后的 vLLM 课件

使用 `review-vllm-courseware`。它会同时完成源码核查、问题说明和最终修订文本。

### 先审计，再精确修改 Markdown

先使用 `audit-vllm-courseware` 生成审计报告，再使用 `revise-markdown-from-audit` 把确认的问题应用到 Markdown 文件中。

### 只改善课件表达

使用 `courseware-editor`。它不做 vLLM 源码审计，主要负责课件表达、结构和教学节奏优化。

## 仓库结构

```text
audit-vllm-courseware/
courseware-editor/
review-vllm-courseware/
revise-markdown-from-audit/
```

每个 skill 目录都包含 `SKILL.md`。部分目录还包含 agent 元数据、参考文件或其他辅助材料。

## 注意事项

- vLLM 相关 skill 依赖本地 Python 环境中安装的 vLLM 包。
- vLLM 审计和审阅默认以本地源码为主要依据；除非用户明确要求，否则不使用网页搜索。
- 无法从本地源码确认的声明会被列为待核对或未确认，不会凭记忆静默改写。
- `revise-markdown-from-audit` 只处理审计报告中已经确认的问题，不会顺手做全文重写或风格清理。
