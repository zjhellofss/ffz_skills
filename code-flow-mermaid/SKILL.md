---
name: code-flow-mermaid
description: Draw a clean, readable mermaid flowchart from a code/request-processing flow description. Use when the user describes a code execution path, request lifecycle, module call chain, or numbered step list and asks for a mermaid diagram (画 mermaid 图 / 流程图). Also use when the user mentions /code-flow-mermaid, asks to visualize "重点流程", or wants an existing mermaid diagram restyled (横向/纵向, 简略, 配色).
---

# 代码流程 Mermaid 绘图

根据用户描述的代码执行路径、请求生命周期、模块调用链或编号步骤列表，产出一张**美观、清晰、只展示重点**的 mermaid 流程图。

# 输入

用户会提供以下之一：

- 一段代码流程的文字/编号描述（如「1. 路由进入 → 2. 适配 → 3. 转发…」）
- 一段源码片段 + 需求
- 一张已有的 mermaid 图 + 改样式的要求（横向、简略、换配色等）

若信息不足以画图，先简短询问缺失的关键环节；否则直接产出。

# 核心原则

## 1. 只画重点

- 抓住主干链路，不逐行翻译代码。合并琐碎步骤，突出关键节点、跨进程/跨模块交接点、分支判定点。
- 节点标签精炼：**函数名/动作 + 一行说明**，用 `<br/>` 换行控制宽度。避免整句长文本溢出边框。
- 用户说「简略」时，进一步压缩标签文字并合并次要节点。

## 2. 结构清晰

- 用 `subgraph` 圈出逻辑边界（如「主进程」「子进程」「单请求路径」「批请求路径」），并加中文标题。
- 分支判定用菱形节点 `{"stream?"}` / `{"条件?"}`，两条边分别标 `是`/`否`。
- 起点、终点用圆角节点 `([...])` 区分于中间处理节点 `[...]`。
- 跨进程、跨模块的边加标注（如 `-->|ZMQ|`、`-->|异步返回|`），点明交接机制。

## 3. 方向与布局

- 默认纵向 `flowchart TD`；用户要求「横向」时用 `flowchart LR`。
- 横向主布局下，为控制宽度，可让 `subgraph` 内部用 `direction TB` 纵向排列，subgraph 之间横向展开。
- 避免边过度交叉；判定分支尽量同侧展开。

## 4. 配色（美观关键）

用 `classDef` 为不同逻辑区块上柔和的成套配色（浅底 + 同色系描边 + 深色文字），并把节点 `class` 到对应样式。推荐调色板：

```
classDef m fill:#e3f2fd,stroke:#1976d2,color:#0d47a1;  %% 蓝 — 主进程/主路径
classDef s fill:#fff3e0,stroke:#f57c00,color:#e65100;  %% 橙 — 子进程/次路径
classDef r fill:#e8f5e9,stroke:#388e3c,color:#1b5e20;  %% 绿 — 响应/结果处理
classDef e fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c;  %% 紫 — 起点/终点
```

同一逻辑区块用同一配色；起点终点单独一色。可按图的语义增减色系，但保持「浅底+同色描边+深字」的成套风格。

# 输出

1. 直接输出一个 ` ```mermaid ` 代码块，语法必须合法（判定节点文字用引号包裹，如 `{"stream?"}`；中文标签安全）。
2. 图后附 2～3 句要点说明，点出图里强调了哪些重点（如主链路、跨进程交接、分支判定），不逐节点复述。

# 改样式请求

当用户对已有图提出调整时，只改被要求的维度，其余保持：

- 「横向」→ 改 `TD` 为 `LR`，subgraph 内部酌情 `direction TB`。
- 「简略」→ 压缩标签、合并次要节点。
- 「字太长/超出范围」→ 缩短每个标签文字，多用 `<br/>` 断行。
- 「换配色」→ 调整 `classDef` 调色板，保持成套风格。

# 校验清单

产出前自检：

- [ ] 语法合法，判定节点已用引号
- [ ] 有 subgraph 边界与中文标题
- [ ] 关键交接点/分支已标注
- [ ] 应用了成套 `classDef` 配色，起点终点独立配色
- [ ] 标签精炼、无溢出风险
- [ ] 方向符合用户要求（默认 TD）
