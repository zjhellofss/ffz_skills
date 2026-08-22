# 打分输入与事实契约（v2）

## 1. 两层输入

正式评级必须同时有两张表：

1. `facts.csv`：遵循 `caiwu-fenxi/references/data-contract.md` 的事实账本，保存期间、范围、归属、单位、审计状态、精确来源定位、公式和计算依赖。
2. `score-input.csv`：把事实映射到本规则的 17 个核心评分槽位、6 个结构性筛查和预警槽位。

旧版 `company,subsector,metric,value,status,source` 长表仍可用 `--mode compat` 复算，但只能输出 `LEGACY_DIAGNOSTIC / N/R`，不能发布正式评级或排名。不得从旧 `source` 自由文本自动猜测页码、单位或口径。

## 2. v2 score-input.csv

必需表头：

```text
company,entity_id,subsector,fy,peer_group,metric,value,unit,status,nm_reason,fact_id,input_fact_ids,comparability_status,business_scope_status,semiconductor_revenue_share,calibration_status,source,notes
```

字段规则：

- `entity_id`：一次评分的稳定实体 ID。分部评分必须使用独立 ID。
- `subsector`：`equipment/materials/foundry/idm/osat/fabless/eda/ip`。EDA/IP 自 v2.2 为独立子行业,不再套用 Fabless 代理规则。
- `fy`：使用 `FY2025` 形式；正式评级只接受 FY 审计口径。本地季度诊断可用 `2026Q1`。
- `peer_group`：同业池 ID，默认 `<subsector>-cn-a`；排名还会强制匹配子行业和 FY。
- `value`：从原始字符串解析为有限 `Decimal`；禁止 `NaN/Infinity`。
- `unit`：百分比使用 `percent` 且输入百分点数，如 12.5% 输入 `12.5`；倍数使用 `ratio`，如 72.6% 的收现比输入 `0.726`；金额使用明确单位。
- `fact_id`：正常数值或已核查 flag 对应的事实 ID，值、单位、公司和指标名必须一致。
- `input_fact_ids`：扭亏/转亏、N/M、N/A 和三年 CAGR 的证据事实，以分号分隔。三年 CAGR 必须列四个完整 FY 端点。
- `comparability_status`：`comparable/limited/not_comparable/unknown`。
- `business_scope_status`：`pure_play/segment_scored/diversified_unallocated/unknown`。
- `semiconductor_revenue_share`：0–100。低于 70% 不得标为 `pure_play`；无法进行同口径分部评分时只能给诊断分。
- `calibration_status`：`calibrated/uncalibrated`。未校准仍可给“规则评级”，但不得声称具有统计意义。
- `source`：仅作兼容展示；v2 的权威来源来自事实账本。

同一 `(company,entity_id,fy,metric)` 只能出现一次。所有 status 都参与重复检查；不得用一行 `missing/N/M` 和另一行数值规避唯一性。
严格模式必须显式列出全部 17 个核心槽位；`missing` 也必须写受控原因，不能靠省略行隐藏缺口。现金转换至少显式列出三年项，只有历史不足并回退时再列当前 FY 项。前五客户/供应商两项自 v2.1 起为预警槽位,不计入核心槽位,但仍应作为预警提供。

## 3. 状态机

### 核心指标

| status | value | 处理 | 严格证据 |
|---|---|---|---|
| `present` | 必填 | 计分 | `fact_id` |
| `missing` | 必须为空 | 不计分，保留分母 | 必填受控 `nm_reason` |
| `not_meaningful` | 必须为空 | 不计分，保留原始覆盖率分母 | `nm_reason` + `input_fact_ids` |
| `not_applicable` | 必须为空 | 仅从适用口径分母剔除 | `business_not_applicable/rule_exempt` + 证据 |
| `turnaround` | 必须为空 | 仅 `nps_growth` 固定 4 分 | 当前与上期扣非利润事实，当前>0、上期≤0 |
| `turn_loss` | 必须为空 | 仅 `nps_growth` 固定 1 分 | 当前与上期扣非利润事实，当前≤0、上期>0 |

`not_meaningful` 的原因码：`negative_denominator/zero_denominator/near_zero_denominator/sign_change/turnaround_window/scope_break/acquisition_break/not_comparable`。未披露不是 N/A。

### 结构性布尔筛查

- `checked_clear`：有证据地核查为否，value 留空或填 0。
- `triggered`：有证据地触发，value 留空或填 1。
- `missing`：未知；不扣分，但阻断正式/暂定评级。
- `not_applicable`：仅在规则确实不适用且有证据时使用。

结构性风险必须是“已触发 / 已核查未触发 / 未知”三态，缺行绝不等于 0。

## 4. 17 个核心评分槽位

### D1 成长持续性

1. 当前 FY 营收 YoY%：`rev_growth`
2. 三年区间营收 CAGR%：`rev_cagr_3y`
3. 当前 FY 扣非归母净利润 YoY%：`nps_growth`
4. 三年区间扣非归母净利润 CAGR%：`nps_cagr_3y`

“三年 CAGR”指 `FY(t-3) → FY(t)` 的三个年度间隔，需要四个完整 FY 端点：`(期末/期初)^(1/3)-1`。扣非利润窗口中任一年度≤0或发生符号变化时记 `not_meaningful`，不能只检查起止点，也不能用两年 CAGR 冒充三年 CAGR。

### D2 盈利能力

5. 合并总口径毛利率%：`gross_margin_total`
6. 归母净利率%：`net_margin_parent`
7. 披露加权平均归母 ROE%：`roe_weighted_parent`

主营毛利率、分部毛利率和合并总毛利率不是同一指标；期末净资产简单 ROE 不能替代披露加权 ROE。

### D3 现金流质量

8. 三年累计 OCF/归母净利润：`cash_conversion_parent_3y`
9. 当前 FY OCF/归母净利润：`cash_conversion_parent_fy`，仅当三年行明确 `missing:insufficient_history` 时回退
10. 长期资产口径 FCF/营收%：`fcf_long_term_assets_margin`
11. 销售商品、提供劳务收到现金/营业收入：`cash_receipts_to_revenue`

三年与单年现金转换共用一个评分槽位且不得同时为 `present`。三年累计利润非正、口径断点或结果较差都不是切换到单年的理由。

`fcf_long_term_assets_margin=(OCF−购建固定资产、无形资产和其他长期资产支付的现金)/营收`。它不同于 pure-PPE FCF，二者不得混用。

### D4 资产负债健康

12. 负债合计/资产合计%：`debt_to_assets`
13. 流动资产/流动负债：`current_ratio`
14. 净现金/总资产%：`net_cash_to_assets`

`net_cash=现金及现金等价物−有息负债`。不得默认加入交易性金融资产、理财或受限存款；纳入经核实的其他流动性资产时必须改名 `net_liquidity`，且不能送入本默认槽位。

### D5 盈利质量

15. 扣非归母净利润/归母净利润：`recurring_parent_profit_ratio`
16. 已对账政府补助当期损益影响/利润总额%：`government_grant_pnl_ratio`
17. 资本化研发支出/研发投入合计%：`rd_capitalization_rate`

补助分子只汇总可证明互斥的当期损益影响。其他收益、营业外收入、成本冲减、递延收益、现金收款和非经常项目不得未经对账相加。

### D6 创新投入

17. 研发费用/营业收入%：`rd_expense_intensity`

核心槽位总数为 17，因为两种现金转换只计一个,且 v2.1 已将前五客户/供应商两项移出核心正分槽位。默认研发强度只接受研发费用口径，不以研发投入总额替代。

原“前五大直接开票客户收入占比”(`top5_billed_customer_revenue_ratio`)和“前五大供应商采购占比”(`top5_supplier_purchase_ratio`)自 v2.1 起为预警项(见 §5),只提示不扣分,不计入 D6 正分,也不计入核心覆盖率分母。客户集中度是直接客户/经销商集中度，不等于终端需求集中度。

## 5. 结构性筛查与预警

必须显式完成六项结构性筛查：

- `goodwill_to_parent_equity`
- `largest_billed_customer_revenue_ratio`
- `largest_supplier_purchase_ratio`
- `performance_commitment_flag`
- `audit_issue`
- `debt_default`

最大供应商占比较高表示“供应商集中风险”，不能仅凭占比写成独家或单一来源依赖。

预警项：

- `operating_cash_flow`
- `inventory_days_change`
- `impairment_to_pbt`
- `da_to_revenue`
- `top5_billed_customer_revenue_ratio`(阈值>60%,v2.1 由原 D6 正分降级)
- `top5_supplier_purchase_ratio`(阈值>60%,v2.1 由原 D6 正分降级)

预警缺失要显示筛查覆盖率，不得表述为“无预警”；但按当前规则不阻断评级。前五占比预警与结构性筛查里“最大直接客户/供应商>40%”口径不同,不构成对同一风险的重复扣分。

## 6. 旧指标名兼容

兼容模式会映射旧名，例如 `gross_margin→gross_margin_total`、`cash_conv→cash_conversion_parent_fy`、`fcf_margin→fcf_long_term_assets_margin`、`net_cash_ratio→net_cash_to_assets`、`subsidy_dep→government_grant_pnl_ratio`。严格模式拒绝旧名，避免把历史含混口径升级成正式事实。

## 7. 从 facts.csv 生成评分输入

不要手工把原始科目抄进 `score-input.csv`。运行：

```bash
python3 scripts/prepare_score_input.py \
  --facts facts.csv \
  --source-root /path/to/source-files \
  --subsector equipment \
  --fy FY2025 \
  --peer-group equipment-cn-a \
  --comparability-status comparable \
  --business-scope-status pure_play \
  --semiconductor-revenue-share 100 \
  --out-dir /path/to/prepared
```

资产负债等时点科目既接受 `FY2025`，也接受 `2025-12-31`/`instant`。不要因为期间标签不同就把 D4 打成缺失。

再打分：

```bash
python3 scripts/score.py /path/to/prepared/score-input.csv \
  --mode strict \
  --facts /path/to/prepared/facts.scored.csv \
  --source-root /path/to/source-files \
  --out-dir /path/to/output
```

输出包包含逐指标明细、汇总、同业排名、规则/输入哈希、事实快照和运行 manifest。不得手工改写脚本结果；修正输入后必须整包重跑。
