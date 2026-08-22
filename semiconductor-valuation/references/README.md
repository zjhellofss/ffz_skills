# 数据接口与字段口径

## 行情(腾讯 qt.gtimg.cn,GBK 编码)
- URL: `https://qt.gtimg.cn/q=sh688019,sz002371,...`
- 字段(按 `~` 分隔):[1]简称、[3]最新价、[39]PE-TTM、[46]市净率(PB)、[79]近1年涨幅%
- 现价、PE-TTM、PB、1年涨幅以该源为准;东财历史序列不覆盖这些字段。
- 腾讯缺失时才回退东财 `RPT_VALUEANALYSIS_DET` 最后一条收盘价/PE/PB,并在输出 `price_source` 标注 `eastmoney_hist_fallback`。
- 代码格式 `688019.SH` / `002371.SZ` / `xxxx.BJ`;港股不在本 skill 覆盖范围。

## 一致预期(东财 RPT_WEB_RESPREDICT)
- URL: `https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_WEB_RESPREDICT&filter=(SECURITY_CODE="688019")`
- 字段:YEAR1-4、YEAR_MARK1-4(A=已实现,E=预测)、EPS1-4、RATING_ORG_NUM、RATING_BUY_NUM、RATING_ADD_NUM。
- 不要把 EPS1 固定解读成 2025A。年份以 YEAR* 为准;脚本同时保留 `eps25a`/`eps26e`/`eps27e`/`eps28e` 作为按公历年的便捷字段。
- `EPS0`:最近一期 YEAR_MARK=A 且 EPS>0;若无,则最早一期 EPS>0 的预测年。
- 无覆盖(次新/亏损)返回空 → 前瞻PEG/DCF 相应缺失。

## 历史估值(东财 RPT_VALUEANALYSIS_DET)
- URL: `https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_VALUEANALYSIS_DET&filter=(SECURITY_CODE="688019")`
- 每日一行 PE_TTM/PB_MRQ/CLOSE_PRICE,按 TRADE_DATE 降序取 2000 条;分位用**当前腾讯 PE/PB**在 3年/5年窗口中低于该值的样本占比。
- 次新(历史<3年)分位参考意义弱;港股/退市可能无数据。

## 口径约定
- 营收 PEG = PE_TTM ÷ 营收增速%,进入估值分;营收增速由 `--rev-g` 传入;
- 前瞻 PEG = (现价/下一预测年EPS) ÷ 一致预期 EPS 增速%,只展示,不进入估值分;
- 「无意义」规则:PE<0、PE>500、增速≤0 或 >200%;
- `--quality` 必须配 `--rating-state=FORMAL|PROVISIONAL`;`N/R` 诊断分拒绝进入三维综合分;
- 增长分缺单项时按可用项重归一化,不填中性 3 分;三项都缺则增长分与综合分都不输出;
- `--risk` 只改 DCF 折现率(9%/10%/12%),不使用未实现的要求回报或安全边际字段;
- 三维权重 50/30/20、档位阈值、DCF 折现率与情景倍数均为分析约定(uncalibrated);
- 所有输出标注风险偏好参数,可复现。
