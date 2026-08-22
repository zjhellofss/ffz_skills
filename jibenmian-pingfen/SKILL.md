---
name: jibenmian-pingfen
description: >-
  Score and rank semiconductor supply-chain companies on fundamental quality
  with a subsector-differentiated 1-5 ruleset, validated caiwu-fenxi fact
  ledgers, explicit data/evidence coverage, structural-risk gates, reproducible
  score details, and same-subsector FY peer cohorts. Use for fundamental scores,
  grades, rankings, peer comparisons, weighted/red-flag reviews, or ROE DuPont
  analysis across equipment, materials, foundry, IDM, OSAT, fabless, EDA, and IP firms.
  Legacy metric CSVs remain diagnostic only. Keep disclosed fact, calculation,
  and analytical convention separate; do not provide price targets or buy/sell
  ratings.
---

# 半导体产业链基本面评分

## 定位与硬边界

把经验证的 FY 财务事实转换为结构化 1–5 分、规则等级和同业 cohort。把阈值、权重和等级称为**分析约定**，不称为会计规则或统计评级。高分不等于“该买”，低分不等于“该卖”；不输出目标价、估值结论或买卖建议。

使用规则 v2.2.0。机器执行值以 `references/rules-v2.json` 为唯一配置源。两位小数用于复算，不代表估计精度。未完成年度样本校准时使用“规则评级”,`calibration.status` 保持 `uncalibrated`,不得宣称具有统计意义。

严格区分：

- `公司披露事实`：来自 `caiwu-fenxi` 事实账本；
- `计算事实`：有公式和 `input_fact_ids`，可重算；
- `评分约定`：命中的阈值、权重、扣分和等级；
- `分析判断`：驱动、风险和可比性解释。

## 必读资源

按任务读取并遵循：

- 准备输入或解释口径：`references/metric-inputs.md`
- 打分：`references/scoring-rubric.md` 和 `references/rules-v2.json`
- 判断资格、扣分和排名：`references/weights-and-flags.md`
- 做 ROE 分解：`references/dupont.md`
- 验证端到端运行：`references/worked-example.md`

## 路径路由

三条路径互斥，不要混用事实账本：

| 用户给的材料 | 走哪个 skill | 产物 |
|---|---|---|
| 年报 PDF、附注、MD&A | `caiwu-fenxi` → 本 skill | 正式/暂定 FY 规则评级 |
| `/home/fss/data` 结构化 CSV | `jibenmian-pingfen-local-data` | 本地诊断；缺结构筛查时通常 `N/R` |
| 飞书目录里的已有报告 | `compare-semiconductor-fundamentals` | 飞书横比 0–100 分，**不是**本规则的 A/B+/B |

季报 PDF 只做 `caiwu-fenxi` 财务分析，不要送进本 skill 求正式评级，也不要改走 local-data。本地 CSV 的季度 TTM 只属于 local-data。`compare` 的名次不得改写成 `FORMAL A`。

同业默认 `peer_group=<subsector>-cn-a`。Foundry、IDM、OSAT 即使共享权重也分池。多公司排名必须同一 `subsector + FY + peer_group + calibration_status + rules_version`。

## 工作流

### 1. 建立或接收事实账本

若用户提供原始年报或已审计 FY 财报，先使用 `caiwu-fenxi`：

1. 建立 `facts.csv`；
2. 核对资产负债表、利润表、现金流量表和关键注释；
3. 保留 period、period_type、scope、attribution、unit、currency、audit_status、精确 source locator、formula 和 input fact IDs；
4. 运行其 facts strict validator 并解决全部错误/警告。

不要从旧报告正文或评分结果反推“权威事实”。同业每个值必须来自该公司的已验证事实账本。

### 2. 确认评分实体和可比性

为每个评分实体确定：

- 子行业：`equipment/materials/foundry/idm/osat/fabless/eda/ip`；
- FY、合并或分部范围、同业 `peer_group`；
- `comparability_status`；
- `business_scope_status` 和半导体主营收入占比。

单一主营收入占比不足 70% 时优先做完整分部评价。无法获得同口径分部利润、资产负债和现金流时，保留合并诊断分但不得包装成纯半导体正式评级或排名。记录并购并表、剥离、重述、会计政策和币种变化；不可比时不得仅靠标签硬归类。

### 3. 准备 v2 score-input.csv

不要手填评分长表。先运行：

```bash
python3 scripts/prepare_score_input.py \
  --facts facts.csv \
  --source-root /path/to/source-files \
  --company 安集科技 \
  --subsector materials \
  --fy FY2025 \
  --peer-group materials-cn-a \
  --comparability-status comparable \
  --business-scope-status pure_play \
  --semiconductor-revenue-share 100 \
  --out-dir /path/to/prepared
```

脚本会从原始科目计算可重算槽位，缺证据的槽位写成受控 `missing/not_meaningful`，并写出 `score-input.csv` 与补齐后的 `facts.scored.csv`。资产负债等时点科目既接受 `FY2025` 也接受 `2025-12-31`/`instant`。再按 `references/metric-inputs.md` 检查 17 个核心槽位、6 个结构性筛查和预警槽位。每个正常数值引用 `fact_id`；扭亏/转亏、N/M、N/A 和三年 CAGR 引用 `input_fact_ids`。

执行以下约束：

- 三年 CAGR 使用四个完整 FY 端点和三个年度间隔；扣非利润窗口任一年度≤0时记 `not_meaningful`。
- 三年现金转换优先；只有明确的 `insufficient_history` 才回退当前 FY。
- 使用长期资产现金支出口径 FCF，不与 pure-PPE FCF 混用。
- 严格净现金不默认加入交易性金融资产或理财；扩展口径改称净流动性且不送入默认槽位。
- 研发强度使用研发费用口径；补助分子先做非重叠对账。
- 客户集中度保留直接客户/经销商口径，不推断终端需求集中度。
- 高供应商占比称集中风险，不凭占比声称独家供应。

禁止用记忆、预测或无来源估算填补。禁止用 `not_applicable/N/M` 缩小分母来抬高置信度。

### 4. 严格计算并保存完整输出包

运行：

```bash
python3 scripts/score.py /path/to/prepared/score-input.csv \
  --mode strict \
  --facts /path/to/prepared/facts.scored.csv \
  --source-root /path/to/source-files \
  --out-dir /path/to/score-output
```

严格模式必须 fail closed：旧指标名、重复行、状态/数值矛盾、非有限数、单位/比例疑似错误、事实值不一致、公式或 locator 错误都先修输入再重跑，不自动猜测或缩放。

检查输出：

- `score_detail.csv`：逐指标值、状态、命中档、分数、fact ID、公式、审计状态和来源；
- `score_summary.csv`：六维、四类覆盖率、结构/预警覆盖率、诊断档位、发布评级和资格原因；
- `ranking.csv`：仅正式、同子行业、同 FY、同 peer group 的 cohort；
- `score_manifest.json`：规则/引擎/输入/产物哈希和运行约定；
- 输入事实快照。

不得手工覆盖脚本结果。发现错误时修正事实或评分映射，保留原因并整包重跑。

### 5. 区分诊断分、评级和排名

按 `references/weights-and-flags.md` 执行：

- `FORMAL`：高置信度正式规则评级，可排名；
- `PROVISIONAL`：带 `*` 的暂定规则评级，不排名；
- `N_R`：只显示诊断分；
- `LEGACY_DIAGNOSTIC`：旧 CSV 可复算，但发布评级固定为 `N/R`。

同时报告原始覆盖率、适用覆盖率、证据覆盖率和已评分证据覆盖率。六项结构性风险使用 `triggered/cleared/unknown`；unknown 不扣分，但阻断正式和暂定评级。

排名只纳入 `FORMAL`，匹配子行业、FY、peer group、校准状态和规则版本。总分以每档首名为锚，分差 `<0.10` 归为同档；差值恰好 0.10 开新档。Foundry、IDM、OSAT 即使共享权重也默认分别排名。跨子行业只能做明确警示的概览。

### 6. 做 DuPont 对账

需要 ROE 解释时完整读取 `references/dupont.md`。使用期初/期末平均资产和平均归母权益，计算归母净利率 × 总资产周转率 × 权益乘数，并与披露加权 ROE 对账。

用 `scripts/dupont.py` 读取 fact-ID 映射和同一份已验证 facts.csv，保存 `dupont.csv`、manifest 与输入快照；不要在报告中手工重算另一套数值。

同时检查少数股东权益：报告归母权益乘数与总权益乘数；少数股东权益重大时说明归母口径放大不等于债务杠杆。合并亏损而归母盈利时同时展示总权益 ROE 或 ROIC，不用归母 ROE 掩盖集团整体亏损。

### 7. 写结论

每家公司输出：

1. 总分、诊断档位、发布评级状态；
2. 四类核心覆盖率、结构/预警覆盖率和未解决门控；
3. 六维主要驱动及事实 ID；
4. 结构性扣分的实际值、来源、名义/实际扣分和评级上限；
5. 不重复扣分的预警和 unknown；
6. 同业 cohort、名次/同档及不可比限制；
7. “非投资建议”声明。

## 兼容模式

只有旧长表时可运行：

```bash
python3 scripts/score.py legacy.csv --mode compat --out diagnostic.csv
```

兼容 UTF-8 BOM、旧指标名、空 status、`nm/n/m` 和省略缺失行，但仍拒绝 NaN/Infinity、矛盾重复和无效数值。旧数据中无单位的 `ocf=±1` 只按正负号哨兵解释，不伪装成金额。输出总分用于排查或历史复算；不要把 `diagnostic_grade` 当正式评级，不要生成同业排名。

## 可视化

需要图形时使用 Python 生成六维雷达图、正式 cohort 条形图或 DuPont 三因子图。图中标明规则版本、FY、评级状态、可比 cohort 及披露/计算属性。不要用 Mermaid 绘制数据图。

## 局限

- 本框架是 FY 快照，不能替代产品、份额、良率、订单、产能利用率和竞争格局分析。
- D6(v2.1 起为单一“创新投入”)不是完整护城河评价；不要把主观竞争力判断塞入财务量化分。客户/供应商集中风险由结构性筛查(最大单一占比)扣分和预警(前五占比提示)两层处理,不再计入 D6 正分。
- 阈值至少每年按同子行业 FY 样本校准；未校准时保留 `uncalibrated`。
- EDA/IP 自 v2.2 起有独立权重与定制阈值(毛利率、营收增速、研发强度),可进入各自子行业的正式评级与排名,不再套用 Fabless 代理规则。但其阈值仍是专家先验、未经样本校准(见 `weights-and-flags.md` §9),且 EDA/IP 同业样本通常偏少;IP 公司若混大量设计服务,需先确认口径可比再入正式 cohort,否则只做诊断。
