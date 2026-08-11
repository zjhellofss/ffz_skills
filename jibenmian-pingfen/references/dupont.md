# ROE 杜邦三因子分解与少数股东权益

## 1. 归母口径公式

```text
归母 ROE（简单平均口径）
= 归母净利率 × 总资产周转率 × 归母权益乘数

归母净利率 = 归母净利润 / 营业收入
总资产周转率 = 营业收入 / 平均总资产
归母权益乘数 = 平均总资产 / 平均归母净资产
平均 = (期初 + 期末) / 2
```

三因子乘积代数上等于 `归母净利润/平均归母净资产`。把它与公司披露的**加权平均归母 ROE**对账；两者不同不自动表示数据错误。

## 2. 确定性输入与脚本

先准备通过 `caiwu-fenxi` strict validator 的 `facts.csv`，再建立一行一个实体/FY 的 fact-ID 映射：

```text
company,entity_id,fy,scope,
revenue_fact_id,net_profit_parent_fact_id,net_profit_total_fact_id,
total_assets_open_fact_id,total_assets_close_fact_id,
parent_equity_open_fact_id,parent_equity_close_fact_id,
total_equity_open_fact_id,total_equity_close_fact_id,
disclosed_roe_fact_id,notes
```

运行：

```bash
python3 scripts/dupont.py assets/example-dupont-input.csv \
  --facts assets/example-dupont-facts.csv \
  --source-root assets \
  --out-dir /path/to/dupont-output
```

脚本强制检查公司、FY、scope、metric、attribution、审计状态、金额单位和币种。期初/期末资产和权益必须使用时点事实；流量使用当前 FY。分母≤0时输出 `N/M_NONPOSITIVE_DENOMINATOR`，不构造失真的乘数或 ROE。

输出 `dupont.csv`、运行 manifest、输入和事实快照。禁止手工复制舍入后的报表数字再做二次计算。

## 3. 对账差异

脚本使用以下分析约定：

- 绝对差≤1.00 个百分点：`matched`；
- >1.00 且≤2.00 个百分点：`review`；
- >2.00 个百分点：`explain`。

常见原因：

1. 年内增发、GDR 或回购使简单期初/期末平均不同于时间加权净资产；
2. 披露 ROE 使用监管加权口径；
3. 追溯调整、合并范围或归属口径不一致；
4. 使用期末净资产、总权益或总净利润误替代归母加权口径。

对账状态只是复核门槛。差异较大时回到 fact IDs 检查口径并写明原因，以披露加权 ROE 为准。

## 4. 少数股东权益失真

归母权益乘数的分子是全部合并资产，分母只含归母权益。当 FAB 扩产主体或并购子公司获得外部股东注资时，少数股东权益会使归母权益乘数高于总权益乘数，这部分放大不是债务杠杆。

同时计算：

```text
总权益乘数 = 平均总资产 / 平均所有者权益合计
总权益 ROE = 合并净利润 / 平均所有者权益合计
平均少数股东权益 = 平均总权益 − 平均归母权益
少数股东权益占比 = 平均少数股东权益 / 平均总权益
```

默认把少数股东权益占平均总权益绝对值≥20%标为 `major_nci_flag=true`。20%是分析预警阈值，不是会计准则；报告实际占比和两种权益乘数，不只写 flag。

若合并净利润<0而归母净利润>0，标记 `group_loss_parent_profit_flag=true`，同时展示总权益 ROE 或 ROIC，不能用正的归母 ROE 掩盖集团整体亏损。少数股东权益为负时同样报告实际值并解释。

## 5. 输出解释

至少展示：公司、FY、归母净利率、资产周转率、归母权益乘数、三因子 ROE、披露加权 ROE、对账差、总权益乘数、总权益 ROE、NCI 占比和两个 flag。

把“高毛利驱动、周转驱动、归母权益乘数放大、重资产低周转”等表述标为计算或分析判断，并链接对应 fact IDs。不要跨不同行业结构直接比较乘数高低。
