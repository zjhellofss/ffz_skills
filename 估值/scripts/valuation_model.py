#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三维估值模型: 综合分 = 质量(50%) + 增长确定性(30%) + 估值安全边际(20%)

输入 CSV 列:
  company, quality_score, rev_growth, rev_cagr_3y, nps_growth, pe_ttm, pb, return_1y
可选列(提供后估值分优先用历史分位): pe_pct, pb_pct  (0-100, 低分位=便宜)
缺失字段留空即可; 缺失按最保守档处理, 并输出 note。

用法:
  python3 valuation_model.py input.csv --out-dir /tmp/valuation-out
  python3 valuation_model.py input.csv --weights 0.5,0.3,0.2 --out-dir out
"""
import argparse, csv, os, sys
from decimal import Decimal, ROUND_HALF_UP

def fnum(v):
    try:
        f = float(str(v).replace(",", ""))
        return f
    except (TypeError, ValueError):
        return None

def growth_band(v, hi5, hi4, hi3, hi2):
    """高好指标: 达到下限即进入该档"""
    v = v if v is not None else -999
    if v >= hi5: return 5
    if v >= hi4: return 4
    if v >= hi3: return 3
    if v >= hi2: return 2
    return 1

def low_band(v, lo5, lo4, lo3, lo2):
    """低好指标: 不超过上限即进入该档"""
    v = v if v is not None else 10 ** 9
    if v <= lo5: return 5
    if v <= lo4: return 4
    if v <= lo3: return 3
    if v <= lo2: return 2
    return 1

def percentile_band(pct):
    """历史分位低好: <20→5, <40→4, <60→3, <80→2, else 1"""
    p = pct if pct is not None else 99
    if p < 20: return 5
    if p < 40: return 4
    if p < 60: return 3
    if p < 80: return 2
    return 1

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv")
    ap.add_argument("--weights", default="0.5,0.3,0.2", help="质量,增长,估值权重(逗号分隔, 默认0.5,0.3,0.2)")
    ap.add_argument("--out-dir", default="valuation_out")
    ap.add_argument("--out", default="valuation_model_output.csv")
    args = ap.parse_args()

    wq, wg, wv = [float(x) for x in args.weights.split(",")]
    if abs(wq + wg + wv - 1.0) > 1e-6:
        raise ValueError("权重之和必须为1")

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    out_rows = []
    for r in rows:
        name = r.get("company") or r.get("name") or ""
        q = fnum(r.get("quality_score"))
        g = fnum(r.get("rev_growth"))
        cagr = fnum(r.get("rev_cagr_3y"))
        nps = fnum(r.get("nps_growth"))
        pe = fnum(r.get("pe_ttm"))
        pb = fnum(r.get("pb"))
        r1 = fnum(r.get("return_1y"))
        pe_pct = fnum(r.get("pe_pct"))
        pb_pct = fnum(r.get("pb_pct"))

        # 质量分: 必须有(缺失时提示)
        q = q if q is not None else 0

        # 增长确定性分
        gs = growth_band(g, 60, 40, 20, 5)
        cs = growth_band(cagr, 25, 15, 8, 0)
        ns = growth_band(nps, 100, 50, 20, 0)
        gr = 0.5 * gs + 0.3 * cs + 0.2 * ns

        # 估值安全边际分
        notes = []
        if pe and 0 < pe < 500 and g and g > 0:
            peg = pe / g
            ps = low_band(peg, 1, 2, 3, 4)
        else:
            ps = 2
            if pe is None or pe <= 0 or pe >= 500:
                notes.append("PE无意义")
            elif not g or g <= 0:
                notes.append("增速缺失/非正, PEG不可算")
        if r1 is None:
            rs = 3
        else:
            rs = 1 if r1 > 400 else 2 if r1 > 300 else 3 if r1 > 200 else 4 if r1 > 100 else 5
        if pb is None:
            bs = 3
        else:
            bs = low_band(pb, 5, 10, 15, 25)

        if pe_pct is not None or pb_pct is not None:
            vs = 0.4 * percentile_band(pe_pct if pe_pct is not None else 50) \
                 + 0.2 * percentile_band(pb_pct if pb_pct is not None else 50) \
                 + 0.2 * ps + 0.2 * rs
            notes.append("估值用历史分位")
        else:
            vs = 0.4 * ps + 0.3 * rs + 0.3 * bs

        if g is not None and g > 60 and pe is not None and 0 < pe < 500:
            notes.append("高增速可能使PEG偏低")

        total = wq * q + wg * gr + wv * vs
        total = float(Decimal(str(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        out = dict(r)
        out["quality_score"] = f"{q:.2f}"
        out["growth_score"] = f"{gr:.2f}"
        out["valuation_score"] = f"{vs:.2f}"
        out["total_score"] = f"{total:.2f}"
        out["note"] = "; ".join(notes)
        out_rows.append(out)

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, args.out)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print(f"{'公司':<10}{'质量':<7}{'增长':<7}{'估值':<7}{'综合':<7}备注")
    for o in sorted(out_rows, key=lambda x: float(x["total_score"]), reverse=True):
        print(f"{o.get('company',''):<10}{o['quality_score']:<7}{o['growth_score']:<7}{o['valuation_score']:<7}{o['total_score']:<7}{o['note']}")
    print(f"\n输出已写入 {path}")

if __name__ == "__main__":
    main()
