---
name: semiconductor-valuation
description: >-
  Value semiconductor supply-chain companies with market data (PE-TTM/PB/1y
  return), historical PE/PB percentiles (3y/5y), sell-side consensus EPS and
  forward PEG, a 3D composite score (quality 50% + growth 30% + valuation 20%),
  and DCF bear/base/bull scenarios with parameterized discount rate and risk
  preference. Use for valuation screening, "is it expensive" checks, price-level
  vs DCF positioning, forward PEG, PE/PB percentile review, or composite
  rank across a list of A-share semiconductor companies. Takes quality/growth
  scores (e.g. from jibenmian-pingfen) as optional inputs; outputs reproducible
  CSV/JSON. Research screening only — no price targets or buy/sell ratings.
---

# 半导体估值(行情 + 分位 + 一致预期 + 三维综合 + DCF 三情景)

## 定位与硬边界

把市场数据(PE-TTM/PB/1年涨幅)、历史分位、卖方一致预期与基本面分(可选,来自 `jibenmian-pingfen`)组合成估值判断。把权重、档位阈值、折现率、情景倍数称为**分析约定**,不称为定价模型。**不输出目标价或买卖指令**;输出的是"相对贵不贵 + 现价在 DCF 情景中的位置 + 相对排序",是研究筛选工具。

数据源为公开接口(腾讯行情、东财数据中心),无需密钥;行情为调用时最新收盘。所有数值标注来源与口径,可复现。

严格区分:
- `市场事实`:腾讯返回的 PE-TTM、PB、价格、涨幅(现价与绝对估值以此为准);
- `机构事实`:东财一致预期 EPS 与评级;
- `分析约定`:三维权重、档位阈值、折现率、情景倍数;
- `分析判断`:位置解读、相对排序、贵贱结论。

## 快速使用

```bash
# 基础:只出估值数据(价格/PE/PB/1年涨幅/分位/一致预期PEG/DCF)
python3 scripts/valuation.py --tickers 688019.SH,002371.SZ,603061.SH --out-dir ./out

# 带基本面分(仅 FORMAL/PROVISIONAL; N/R 诊断分不能进综合分)
python3 scripts/valuation.py --tickers 688019.SH,002371.SZ \
  --quality 4.21,3.41 --rating-state FORMAL,FORMAL \
  --growth 3.80,3.10 --risk aggressive --out-dir ./out

# 不传 --growth 时,用营收/扣非增速现场算增长分,并用营收增速算 PEG
python3 scripts/valuation.py --tickers 688019.SH --quality 4.21 \
  --rating-state FORMAL --rev-g 35.2 --rev-cagr 28.1 --nps-g 42.0 \
  --risk conservative --out-dir ./out
```

输出 `valuation_output.csv` + `valuation_output.json`(每家:价格/PE-TTM/PB/1年涨幅、PE/PB 3年5年分位、营收PEG、一致预期 EPS/评级/前瞻PEG、DCF 悲观/基准/乐观/现价位置、三维综合分)。三维综合分仅在同时有质量分与增长分时输出;缺增长输入时不静默填 3 分。

风险偏好 `--risk` **只决定 DCF 折现率**: aggressive 9% / balanced 10% / conservative 12%。

## 模型(分析约定)

### 三维综合分(需质量分 + 增长分)
```
综合分 = 0.5×质量分 + 0.3×增长分 + 0.2×估值分
```
- **质量分**:来自 `jibenmian-pingfen` 六维总分(0-5),且 `rating_state` 必须是 `FORMAL` 或 `PROVISIONAL`。`N/R`、`LEGACY_DIAGNOSTIC`、`QUARTERLY_DIAGNOSTIC` 是诊断分,不得传入 `--quality`;
- **增长分**:优先用 `--growth` 直传;否则 `0.5×营收增速档 + 0.3×三年营收CAGR档 + 0.2×扣非增速档`(各1-5)。缺项不填中性 3 分,按可用项重归一化;三项都缺且非扭亏/仍亏特判时增长分记缺失,综合分不输出;
- **估值分**:`0.4×营收PEG档 + 0.3×涨幅透支档 + 0.3×PB档`(各1-5)。PEG 无意义时该档记 1,不改用前瞻 PEG 顶替。

档位阈值(1-5):
| 档 | 营收增速 | 三年CAGR | 扣非增速 | PEG | 1年涨幅 | PB |
|---|---|---|---|---|---|---|
| 5 | ≥50% | ≥40% | ≥100%/扭亏 | ≤1 | ≤50% | ≤4 |
| 4 | 30-50% | 25-40% | 50-100% | 1-2 | 50-100% | 4-8 |
| 3 | 15-30% | 15-25% | 20-50% | 2-3 | 100-200% | 8-12 |
| 2 | 0-15% | 5-15% | 0-20% | 3-5 | 200-300% | 12-20 |
| 1 | <0% | <5% | <0%/亏损 | >5或N/A | >300% | >20 |

边界值落在更高档(例如涨幅=50%记 5 档,PEG=1 记 5 档),与表格「≤」口径一致。

### PEG
`PEG = PE-TTM ÷ 营收增速%`(用营收增速替代盈利增速,因半导体盈利波动大);**PE<0(亏损)、PE>500(微利)、增速≤0或>200%(低基数失真)时判「无意义」**。营收增速需由 `--rev-g` 传入,脚本不从行情接口推断。

有一致预期时另给 `fwd_peg = 前瞻PE ÷ 一致预期EPS增速%`。前瞻 PE = 现价 ÷ 下一预测年 EPS;EPS 增速相对最近一期为正的实际年(YEAR_MARK=A),否则相对最早一期为正的预测年。`fwd_peg` 同样套用无意义规则,只作一致预期层展示,不进入估值分。

### 历史分位
东财每日 PE_TTM/PB_MRQ 序列(上市以来)只用于分位,不覆盖腾讯现价/PE/PB。分位 = 当前腾讯 PE/PB 在 **3年/5年** 窗口中低于该值的样本占比(%)。腾讯行情缺失时才回退东财历史最后一条,并在 `price_source` 标注。半导体判断贵贱**优先看 PB 分位**(PE 会被周期利润扭曲,如周期顶利润暴增→PE 分位低但 PB 极高)。

### DCF 三情景(一致预期驱动)
```
每股价值 = Σ EPS_t/(1+r)^t + 终值/(1+r)^5   (5年:前3年增速g,4-5年衰减,终值永续)
悲观:增速×0.4,终值2% | 基准:一致预期增速,终值3% | 乐观:增速×1.5,终值4%
```
- `EPS0`:最近一期为正的实际 EPS(YEAR_MARK=A);若无,则取最早一期为正的预测 EPS;
- `g` = EPS0 到第3年的 EPS CAGR;没有 +3 年正值时用可得最长窗口(≥1年),夹在 [3%,60%];其后没有正 EPS 则 DCF 整段缺失;
- `r` 折现率:aggressive 9% / balanced 10% / conservative 12%;
- **现价位置**:低估(≤悲观) / 合理(悲观~基准) / 偏贵(基准~乐观) / 高估(>乐观);
- 局限:一致预期可能滞后(尤其周期股),DCF 对折现率极敏感,终值把 EPS 当全部分配的简化口径,用作**相对标尺**而非绝对目标价。

## 工作流

1. 确认标的与代码(如 `688019.SH` / `002371.SZ` / `603061.SH`,格式 代码.市场;市场仅 SH/SZ/BJ);
2. 可选:先用 `jibenmian-pingfen` 得到每家质量分/增长分。只有 `FORMAL` 或 `PROVISIONAL` 才能传 `--quality` 和 `--rating-state`;本地 CSV/`N/R`/季度诊断分不要送进来。若无现成增长分,传 `--rev-g`/`--rev-cagr`/`--nps-g`(及可选 `--nps-flag`),缺哪项就空着,不要用 3 分顶替;
3. 选定风险偏好 `--risk`(只改 DCF 折现率);
4. 运行脚本,检查输出:确认每家都有行情、分位、一致预期(次新/亏损可能缺失,如实标注);看 `price_source` 是否为腾讯;
5. 输出解读:
   - **估值数据层**:PE/PB 绝对值与分位、1年涨幅、营收PEG → "贵不贵";
   - **一致预期层**:机构覆盖数、评级、前瞻PEG → "市场预期如何";
   - **DCF层**:现价在悲观/基准/乐观中的位置 → "市场已为多少乐观付钱";
   - **综合层**(有质量分且有增长分时):三维排序 → "基本面+估值双高名单"。
6. 结论中区分:质量(基本面)与估值是两件事——"基本面好"≠"现在值得买"(要看现价位置)。

## 边界与局限

1. **不是定价模型**:不给目标价、不算远期一致预期之外的成长;DCF 是相对标尺;
2. **一致预期可能滞后**:周期股(存储/光模块)预期在周期顶偏高、底部偏低,前瞻PEG 需打折;
3. **分位是相对自身历史**:不是绝对便宜;次新(上市<3年)分位样本短、参考弱;
4. **数据为最新收盘/披露**:行情实时,一致预期与历史分位随披露更新;
5. **参数是启发式**:50/30/20、档位阈值、折现率、情景倍数可按偏好调整并注明;
6. **不构成投资建议**:输出为研究筛选工具。

## 参考

- `references/README.md` — 数据接口与字段口径说明
- 与 `jibenmian-pingfen` 配合:质量分来自基本面评分,估值分由本 skill 用营收 PEG + 涨幅 + PB 计算。
