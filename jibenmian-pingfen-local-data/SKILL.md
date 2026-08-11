---
name: jibenmian-pingfen-local-data
description: >-
  Directly read structured listed-company financial CSV data under
  /home/fss/data and score semiconductor supply-chain companies with FY or
  quarterly TTM diagnostics under the jibenmian-pingfen v2.2.0 rules. Use for
  local-data fundamental scores, quarterly tracking, grades, evidence coverage,
  structural-risk gates, same-subsector FY peer comparisons, or FY ROE DuPont
  analysis across equipment, materials, foundry,
  IDM, OSAT, fabless, EDA, and IP firms. Do not extract PDFs and do not use
  caiwu-fenxi facts or intermediate artifacts. Preserve CSV-row lineage,
  distinguish disclosed data from calculations and scoring conventions, and
  do not provide price targets or buy/sell ratings.
---

# 本地财务数据半导体基本面评分

## 硬边界

直接读取 `/home/fss/data/上市公司财务信息` 中按证券代码拆分的 CSV。不要读取年报 PDF，不要调用 `caiwu-fenxi`，也不要接收其 `facts.csv` 作为本 skill 的权威输入。

使用规则 v2.2.0；机器执行值以 `references/rules-v2.json` 为唯一配置源。完整 FY 可以进入年度评级资格判断；Q1/Q2/Q3 只做 TTM 季度诊断，固定输出 `QUARTERLY_DIAGNOSTIC / N/R`。把阈值、权重、扣分和等级称为分析约定。高分不等于“该买”，低分不等于“该卖”；不输出目标价、估值结论或买卖建议。

严格区分：

- `本地披露数据`：定位到原始 CSV 文件、行号和列名；
- `计算事实`：保存公式和 `input_fact_ids`；
- `评分约定`：命中的阈值、权重、扣分和等级；
- `分析判断`：驱动、风险和可比性解释。

生成的 `local-facts.csv` 是本次运行的可审计快照，不是 PDF 提取产物，也不是 `caiwu-fenxi` 中间产物。不得把其他来源的事实账本混入。

## 必读资源

按任务读取：

- 数据目录、选行和字段映射：`references/local-data-contract.md`
- 指标口径与缺失边界：`references/metric-inputs.md`
- 打分阈值：`references/scoring-rubric.md` 和 `references/rules-v2.json`
- 评级资格、扣分和排名：`references/weights-and-flags.md`
- 杜邦分解：`references/dupont.md`

## 工作流

### 1. 确认实体参数

至少确认：

- 证券代码，如 `688981.SH`；
- 子行业：`equipment/materials/foundry/idm/osat/fabless/eda/ip`；
- 完整 FY，如 `2025`；或者季度，如 `2026Q1`；
- 公司名称；省略时以证券代码显示。

只有用户或可靠本地证据支持时，才设置：

- `comparability_status=comparable`；
- `business_scope_status=pure_play`；
- `semiconductor_revenue_share>=70`。

无法确认时保留默认 `unknown` 和占比 `0`，接受 `N/R`，不要为了获得正式评级擅自抬高资格。

### 2. 一键读取、校验和评分

完整 FY：

运行：

```bash
python3 scripts/score_local.py \
  --ticker 688981.SH \
  --company 中芯国际 \
  --subsector foundry \
  --fy 2025 \
  --comparability-status comparable \
  --business-scope-status pure_play \
  --semiconductor-revenue-share 100 \
  --out-dir /path/to/output \
  --with-dupont
```

默认数据入口是 `/home/fss/data`。如数据被移动，使用 `--data-root` 指向 `/home/fss/data` 或其 `上市公司财务信息` 子目录。

脚本必须：

1. 选择完整 FY、合并报表，并优先对齐该 FY 的审计意见公告日；
2. 对同一审计日期的关键字段冲突 fail closed；
3. 用 `Decimal` 计算，不自动缩放百分比或 ratio；
4. 逐项验证原始 CSV 文件、行号、列名、值和计算依赖；
5. 运行规则 v2.2.0 严格评分；
6. 保存源文件哈希、输入快照和输出 manifest。

季度诊断：

```bash
python3 scripts/score_local.py \
  --ticker 688981.SH \
  --company 中芯国际 \
  --subsector foundry \
  --period 2026Q1 \
  --comparability-status comparable \
  --business-scope-status pure_play \
  --semiconductor-revenue-share 100 \
  --out-dir /path/to/output
```

季度只支持 `Q1/Q2/Q3`；Q4 使用完整 FY。季度口径必须是：

1. 增长：当前季度累计值对比上年同期累计值；
2. 利润、现金流、研发等流量：`最近完整 FY + 当前累计 - 上年同期累计`，构造 TTM；
3. 三年 CAGR 和三年现金转换：使用最近的完整 FY；
4. 资产负债指标：使用季度末时点；
5. 季度事实标记 `unaudited`，不得进入正式评级或排名；
6. 季度暂不支持 `--with-dupont`。

### 3. 检查输出

检查：

- `local-source-manifest.json`：数据根目录、源文件哈希、选择约定；
- `local-facts.csv`：本地原始事实和计算事实；
- `score-input.csv`：17 个核心槽位、6 个结构筛查和 6 个预警；
- `score_detail.csv`：逐指标分数、状态、证据和来源；
- `score_summary.csv`：六维、覆盖率、诊断档位、评级资格；
- `ranking.csv`：仅符合规则的正式同业 cohort；
- `score_manifest.json`：规则、输入和产物哈希；
- `dupont/dupont.csv`：完整 FY 使用 `--with-dupont` 时生成。

不得手工覆盖脚本结果。发现错误时修正选行/映射或实体参数，保留原因并整包重跑。

### 4. 处理本地数据缺口

当前本地表通常不能严格支持以下指标：

- 已对账政府补助当期损益占比；
- 当期资本化研发投入占比；
- 最大及前五客户/供应商占比；
- 业绩承诺履约；
- 实质性债务违约。

保持 `missing/unknown`。空白商誉不自动等于零；期末研发支出余额不等于当期资本化研发投入；主营业务构成数据不等于客户/供应商集中度。未知结构风险不扣分，但阻断正式和暂定评级。

### 5. 写结论

每家公司至少输出：

1. 总分、诊断档位、评级状态和资格原因；
2. 原始、适用、证据、已评分证据覆盖率；
3. 六维主要驱动及 fact IDs；
4. 结构性风险的 `triggered/cleared/unknown`；
5. 预警、缺失项和不可比限制；
6. 同业 cohort、规则版本和校准状态；
7. “非投资建议”声明。

排名只纳入完整 FY 的 `FORMAL`，且必须匹配子行业、FY、peer group、校准状态和规则版本。季度诊断不排名。跨子行业只做明确警示的概览。

## 单独准备或验证

只生成本地输入：

```bash
python3 scripts/local_data.py \
  --ticker 688981.SH --subsector foundry --fy 2025 \
  --out-dir /path/to/prepared
```

单独验证来源：

```bash
python3 scripts/validate_local_facts.py \
  /path/to/prepared/local-facts.csv \
  --source-root /home/fss/data/上市公司财务信息
```

严格模式不允许跳过来源校验。

## 局限

- 数据集按证券代码组织但不含稳定公司名称主表，必要时显式传 `--company`。
- 年度模式是 FY 财务快照；季度模式是 TTM 财务诊断。两者都不能替代产品、份额、良率、订单、产能利用率和竞争格局分析。
- 季度累计字段缺失时保持缺失；不使用快报、预告或年化乘数猜算。
- provider 字段不天然等于审计报告附注口径；脚本只使用明确可映射字段，其余保持缺失。
- `uncalibrated` 表示专家规则评级，不代表统计评级。
