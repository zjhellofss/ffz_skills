---
name: iterate-sglang-courseware
description: Iteratively review, explain, refine, and update Chinese SGLang courseware using the locally installed SGLang source as the technical authority. Use when the user is studying an SGLang document and asks questions, requests source-level verification, wants redundant courseware simplified, asks to edit a local Markdown file, requests ASCII flows converted to Mermaid, or asks to precisely update a named section in an existing Feishu/Lark document while preserving unrelated content.
---

# Iterative SGLang Courseware Workflow

围绕同一份 SGLang 课件持续完成技术答疑、源码核查、内容整理、图示生成和文档更新。

## Required skills

根据任务类型读取并应用以下 Skills：

1. 所有课件整理任务：`courseware-editor`
2. 涉及技术判断或源码核查：`review-sglang-courseware`
3. 涉及飞书文档：`lark-doc`
4. 涉及流程图、调用链或字符画：`code-flow-mermaid`
5. 涉及已有飞书画板编辑：`lark-whiteboard`
6. 涉及飞书 SGLang 课件精确替换：`update-sglang-lark-courseware`

完整阅读已选 Skill 的 `SKILL.md` 及其要求的引用文件后再执行操作。

## 1. 判断用户意图

首先将请求归入以下模式。

### 解释模式

适用于“这是什么意思”“为什么这样设计”“举个例子”“A 和 B 有什么区别”“调用链如何串起来”等请求。

只回答问题，不修改本地文件或飞书文档。回答顺序优先采用：

1. 一句话结论；
2. 执行机制；
3. 必要的具体例子；
4. 容易混淆的边界。

### 审阅模式

适用于 `$review-sglang-courseware`、“核对这段是否正确”“根据源码修改”“找出错误和遗漏”等请求。

对照本机安装的 SGLang 源码审阅，输出：

```text
## Findings
## Unconfirmed in Source
## Revised Text
```

审阅模式不更新飞书文档。

### 本地 Markdown 编辑模式

适用于“整理 `/path/to/file.md`”“在原文件中修改”“去重并突出主线”等请求。

先读取文件，再使用 `apply_patch` 在原文件中完成修改：

- 保留与任务无关的用户内容；
- 不覆盖未授权章节；
- 删除重复叙述并突出主调用链；
- 检查标题层级、代码块和 Mermaid 语法；
- 最终报告实际修改的文件路径。

### 飞书更新模式

适用于 `$update-sglang-lark-courseware`、“更新到飞书文档”“替换第 X 节”“用飞书画板替换字符画”等请求。

默认在原位置精确替换用户指定的章节或段落，不追加重复内容。若本轮没有给出文档链接，但当前对话存在唯一且明确的目标文档，可以继续使用该文档；存在多个候选文档时先请求用户确认。

### 草稿模式

适用于“先生成，不要写入”“先让我确认”“只给出修改稿”等请求。

只输出草稿、XML、Markdown 或 Mermaid，不执行任何写操作。

## 2. 技术核查原则

以本机安装的 SGLang 源码为主要技术依据。

### 源码定位

优先使用：

```bash
rg "ClassName|function_name|config_name" <sglang-source>
```

重点核查：

- 类、函数和字段是否真实存在；
- 配置名称、枚举值和默认值；
- 初始化阶段与 Forward 阶段的调用关系；
- Dispatcher、Runner、Quant Method 等组件的职责边界；
- Tensor、路由信息和通信结果由哪个组件产生；
- 普通路径、A2A 路径和融合路径的差异；
- 条件分支及平台约束。

### 信息边界

- 本地源码可以确认的行为使用确定表述；
- Issue 时间、路线图、性能数据和外部项目历史无法从本地源码确认时，放入 `Unconfirmed in Source`；
- 用户未要求联网时不浏览互联网；
- 避免使用“完全解决”“一定最优”“所有场景”等绝对表述；
- 区分算法目标、启发式实现和实际运行效果。

## 3. 课件整理规则

优先按照以下教学顺序组织内容：

1. 概念与作用；
2. 所处执行位置；
3. 核心流程；
4. 组件职责或字段含义；
5. 简短例子；
6. 约束与边界；
7. 一句话总结。

遵循以下写作要求：

- 一个段落只表达一个主要观点；
- 删除前后重复的定义和流程；
- 先讲主线，再展开特殊分支；
- 保留源码标识符的原始拼写；
- 中文术语保持统一；
- 表格用于职责、映射、参数和方案比较；
- 代码块只保留帮助理解的核心代码；
- 避免大段逐行源码注释；
- 不为追求完整而加入与本节无关的背景。

尤其注意区分：

- Logical Expert 与 Physical Expert；
- EPLB 布局算法与运行时副本调度；
- Dispatcher 与 Expert Runner；
- `moe_a2a_backend` 与 `moe_runner_backend`；
- `DispatchOutput`、`RunnerInput` 与 `CombineInput`；
- Standard、显式 A2A 与融合执行路径；
- 初始化阶段创建组件与 Forward 阶段调用组件。

## 4. Mermaid 与飞书画板

以下内容适合转换为 Mermaid：

- 三个及以上连续步骤；
- 调用链或数据生命周期；
- 模块间交接关系；
- 多分支执行路径；
- 一对多映射；
- 初始化阶段与运行阶段的边界；
- 用户提供的字符画。

简单定义、单个条件或两项比较优先使用文字或表格。

图形要求：

- 短主链默认使用 `flowchart LR`；
- 分支较多时使用 `flowchart TD`；
- 节点文字保持简短；
- 使用 `subgraph` 表达模块或阶段边界；
- 采用浅色背景、同色描边和深色文字；
- 图后只补充一小段解释，不逐节点重复。

推荐配色：

```mermaid
classDef blue fill:#e3f2fd,stroke:#1976d2,color:#0d47a1;
classDef orange fill:#fff3e0,stroke:#f57c00,color:#e65100;
classDef green fill:#e8f5e9,stroke:#388e3c,color:#1b5e20;
classDef purple fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c;
```

更新飞书文档时使用 Mermaid Whiteboard：

```xml
<whiteboard type="mermaid">
flowchart LR
    A["起点"] --> B["处理"] --> C["结果"]
</whiteboard>
```

插入后确认返回结果中存在新的 `whiteboard` block，且没有失败或降级警告。

## 5. 飞书精确更新流程

### 5.1 锁定范围

在写入前明确：

- 目标文档；
- 目标标题；
- 整节替换还是局部段落替换；
- 下一个同级或更高级标题；
- 是否需要保留原有图片或画板。

用户提供完整章节并要求更新时，视为授权替换该章节。用户只要求修改一句或一段时，仅修改对应 Block，不重写整节。

### 5.2 获取实时结构

先读取目录：

```bash
lark-cli docs +fetch \
  --doc "$DOC_URL" \
  --scope outline \
  --max-depth 4 \
  --detail with-ids \
  --as user
```

再读取目标章节：

```bash
lark-cli docs +fetch \
  --doc "$DOC_URL" \
  --scope section \
  --start-block-id "$SECTION_ID" \
  --detail full \
  --as user
```

记录原题 Block ID、下一章节 Block ID、目标范围内所有旧 Block ID，以及写入前 Revision ID。

### 5.3 构建替换内容

精准编辑使用 Docx XML。XML 内容必须：

- 从与原文同级的标题开始；
- 正确转义 `<`、`>` 和 `&`；
- 使用原生表格表达映射或比较；
- 使用 Mermaid Whiteboard 表达流程；
- 保持标题编号连续；
- 不携带无关章节内容。

临时文件必须使用 `apply_patch` 创建。

### 5.4 执行替换

先用 `block_replace` 替换原标题 Block：

```bash
lark-cli docs +update \
  --doc "$DOC_URL" \
  --command block_replace \
  --block-id "$SECTION_ID" \
  --content @replacement.xml \
  --as user
```

然后删除写入前记录的旧章节内容 Block：

```bash
lark-cli docs +update \
  --doc "$DOC_URL" \
  --command block_delete \
  --block-id "$OLD_BLOCK_IDS" \
  --as user
```

不得删除下一章节标题。

### 5.5 回读验证

更新后重新获取目录和目标章节，确认：

- 目标标题只出现一次；
- 下一章节仍然存在；
- 标题顺序正确；
- 新表格和画板已经创建；
- 旧版标题、错误术语及冗余内容已经消失；
- 未修改相邻章节；
- Revision ID 已更新；
- 写操作返回 `result: success` 且 `warnings` 为空。

只有实时回读确认成功，才能向用户报告完成。

## 6. 连续对话中的状态管理

- 保留最近一次明确指定的文档链接；
- 保留当前讨论的章节；
- 用户说“这里”“更新到文档”时，优先关联最近讨论的明确段落；
- 用户明确说“不要更新到飞书”时，切换为只读解释模式；
- 用户提供新的文档链接时，将其设为新的目标文档；
- 不将前一份文档的修改自动应用到后一份文档；
- 用户提出修正时，只替换被指出的内容，不重复更新其他段落。

## 7. 失败处理

### 文档目标不明确

存在多个候选文档或章节时，停止写入并请求确认。

### 权限不足

按照 `lark-shared` 的认证流程处理，不绕过权限或确认门禁。

### 写入没有生效

重新获取实时 Block ID 和 Revision ID，检查 Block ID 失效、内容相同、XML 格式错误以及 `failed` 或 `partial_success` 等结果。

### 画板创建失败

检查 Mermaid 语法、XML 特殊字符、`<whiteboard type="mermaid">` 完整性，以及节点标签中未转义的 HTML。

### 相邻内容受到影响

立即停止后续写入，报告影响范围，并使用文档历史恢复或请求用户授权处理。

## 8. 最终交付

### 解释或审阅任务

直接提供结论、修订稿或必要的源码依据。

### 本地文件任务

报告修改的文件、主要整理内容和验证结果。

### 飞书更新任务

报告：

- 更新的准确章节；
- 主要技术修正；
- 新增或替换的画板数量；
- 明确保留的章节边界；
- 最终 Revision ID；
- 飞书文档链接。

保持交付简洁，不重复粘贴已写入文档的全部正文。
