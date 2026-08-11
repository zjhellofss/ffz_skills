# 示例公司 FY2025 财务与基本面分析

## 公司与来源范围

| 来源 | 期间 | 审计状态 | 定位约定 |
|---|---|---|---|
| `FY2025-annual-report.pdf` | FY2025 | audited | one-based PDF page |

本模板展示事实与结论标记；示例值不是现实公司数据。

## 业务、产品与半导体专项

### 半导体价值链与收入模式

示例公司被假设为半导体材料企业；实际分析必须按披露业务重新分类。

### 产品与商业化阶段

示例未提供产品阶段，状态为 `not disclosed`，不据此推断收入贡献。

### 经营 KPI 桥

示例只展示通用财务指标，不强行补入未披露的产能、销量或价格。

### 周期、库存与产能

状态为 `not disclosed`；正式报告应说明缺口对周期判断的限制。

### 订单、认证、验收与收入确认

状态为 `not disclosed`；不得把验证、交付和收入确认视为同一阶段。

### 资本开支、在建工程、转固与折旧

示例采用长期资产现金支出口径的自由现金流，未披露转固计划。

### 供应链、集中度、政策与地域

状态为 `not disclosed`；高集中度不自动等于单一来源依赖。

## 财务快照

| 指标 | 期间 | 数值 | Fact ID |
|---|---|---:|---|
| 营业收入 | FY2025 | 1,000 million CNY | `f_rev` |
| 毛利 | FY2025 | 400 million CNY | `f_gp` |
| 归母净利润 | FY2025 | 100 million CNY | `f_np_parent` |
| 经营现金流 | FY2025 | 250 million CNY | `f_ocf` |

## 盈利能力

FY2025 综合毛利率为 40%，由同口径收入与成本计算。[F:f_gm]
毛利率本身不足以证明价格、产品组合或成本中的哪一项是主因。
[C:margin_01|inference]

## 现金流与资产负债表

经营现金流为 250 million CNY，自由现金流（长期资产现金支出口径）
为 150 million CNY。[F:f_ocf] [F:f_fcf]
期末资产 1,500 = 负债 500 + 权益 1,000 million CNY，勾稽一致。
[F:f_assets] [F:f_liabilities] [F:f_equity]

## 关键附注与会计口径

本示例区分合并净利润 120、归母净利润 100 与少数股东损益 20
million CNY。[F:f_np_total] [F:f_np_parent] [F:f_np_nci]

## 基本面、预期与风险

- 基本面：示例公司的利润与现金流均为正，但这不构成质量保证。
  [C:fundamental_01|calculated]
- 预期：产品、订单和产能信息未披露，不形成正向推断。
  [C:expectation_01|source-stated]
- 风险：经营 KPI 缺失限制了对增长驱动的判断。
  [C:risk_01|inference]

## 风险监控与开放问题

需要补充产品收入、库存结构、客户资格、产能和政府支持的可比披露。

## 附录与证据

- 事实台账：`example-facts.csv`
- 图表规范：`example-chart-spec.csv`
- 验证：`validate_analysis.py facts` 与 `validate_analysis.py report`
