#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""半导体估值工具:行情 + 历史分位 + 一致预期 + 三维综合 + DCF三情景

用法:
  python3 valuation.py --tickers 688019.SH,002371.SZ --quality 4.21,3.41 \
      --rating-state FORMAL,FORMAL --growth 3.80,3.10 --risk aggressive --out-dir /path/to/out

  python3 valuation.py --tickers 688019.SH --quality 4.21 \
      --rating-state FORMAL --rev-g 35.2 --rev-cagr 28.1 --nps-g 42.0 --out-dir /path/to/out

输入:
  --tickers   证券代码,逗号分隔(如 688019.SH,002371.SZ,603061.SH); 市场仅 SH/SZ/BJ
  --quality   基本面分(0-5,来自 jibenmian-pingfen FORMAL/PROVISIONAL),逗号分隔;缺省则只做估值数据
  --rating-state  与 --quality 对应的评级状态,仅 FORMAL 或 PROVISIONAL;诊断分拒绝入综合分
  --growth    增长分(0-5,可选); 不传时若有 --rev-g/--rev-cagr/--nps-g 则现场计算,否则三维综合分缺失
  --rev-g     营收增速%(PEG 与增长分用),逗号分隔
  --rev-cagr  三年营收CAGR%(增长分用),逗号分隔
  --nps-g     扣非增速%(增长分用),逗号分隔
  --nps-flag  扣非状态: normal|turnaround_profit|still_loss|missing,逗号分隔
  --risk      aggressive|balanced|conservative,默认 balanced
              仅决定 DCF 折现率: aggressive 9% / balanced 10% / conservative 12%
  --out-dir   输出目录(生成 valuation_output.csv + valuation_output.json)

数据源(公开接口,无需密钥):
  腾讯行情 qt.gtimg.cn: 当前价/PE-TTM[39]/PB[46]/1年涨幅[79] —— 现价与绝对估值以该源为准
  东财 RPT_WEB_RESPREDICT: 机构一致预期 EPS(YEAR1-4 + YEAR_MARK)+评级
  东财 RPT_VALUEANALYSIS_DET: 历史每日 PE_TTM/PB_MRQ → 3年/5年分位(不覆盖现价)

模型(分析约定,非定价):
  三维综合 = 0.5×质量 + 0.3×增长 + 0.2×估值分
  增长分 = 0.5×营收增速档 + 0.3×三年CAGR档 + 0.2×扣非增速档(1-5)
  估值分 = 0.4×营收PEG档 + 0.3×涨幅透支档 + 0.3×PB档(1-5)
  PEG = PE_TTM ÷ 营收增速%; PE<0/PE>500/增速≤0或>200% 判无意义
  fwd_peg = 前瞻PE(现价/下一预测年EPS) ÷ 一致预期EPS增速%; 同样套用无意义规则
  DCF每股价值 = ΣEPS_t/(1+r)^t + 终值/(1+r)^5(一致预期EPS驱动,悲观/基准/乐观三情景)

非投资建议:输出为研究筛选工具,不给目标价与买卖指令。
"""
import argparse, csv, json, os, subprocess, sys, time
from datetime import datetime

MARKETS = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
NPS_FLAGS = {"normal", "turnaround_profit", "still_loss", "missing"}
ALLOWED_QUALITY_STATES = {"FORMAL", "PROVISIONAL"}
REJECTED_QUALITY_STATES = {
    "N/R", "N_R", "LEGACY_DIAGNOSTIC", "QUARTERLY_DIAGNOSTIC",
}
RISK = {
    "aggressive": {"disc": 9.0},
    "balanced": {"disc": 10.0},
    "conservative": {"disc": 12.0},
}


def curl(url, tries=3, timeout=25):
    for _ in range(tries):
        try:
            out = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                                 capture_output=True, text=True, timeout=timeout + 10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        except Exception:
            pass
        time.sleep(1.5)
    return None


def parse_ticker(t):
    """688019.SH → (688019, sh); 002371.SZ → (002371, sz); 北交所 BJ 映射 bj。"""
    raw = t.strip().upper()
    if "." not in raw:
        raise ValueError(f"代码格式应为 688019.SH, 收到: {t}")
    code, mkt = raw.split(".", 1)
    if mkt not in MARKETS:
        raise ValueError(f"不支持市场 {mkt}(仅 SH/SZ/BJ): {t}")
    if not code:
        raise ValueError(f"缺少证券代码: {t}")
    return code, MARKETS[mkt]


def parse_optional_floats(s, n, name):
    if s is None:
        return None
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != n:
        sys.exit(f"{name} 数量必须与 --tickers 一致")
    out = []
    for p in parts:
        if p == "" or p.upper() in ("NA", "NONE", "-"):
            out.append(None)
        else:
            try:
                out.append(float(p))
            except ValueError:
                sys.exit(f"{name} 含无法解析的数值: {p}")
    return out


def parse_optional_flags(s, n, name, allowed):
    if s is None:
        return None
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != n:
        sys.exit(f"{name} 数量必须与 --tickers 一致")
    out = []
    for p in parts:
        if p == "" or p.upper() in ("NA", "NONE", "-"):
            out.append(None)
        else:
            key = p.strip().lower()
            if key not in allowed:
                sys.exit(f"{name} 取值须为 {sorted(allowed)} 之一, 收到: {p}")
            out.append(key)
    return out


def tof(x):
    try:
        return float(x) if x not in ("", "-", None) else None
    except (TypeError, ValueError):
        return None


def fetch_market(codes):
    """腾讯行情(GBK编码): price/pe_ttm/pb/ret1y/name。现价与绝对估值以此为准。"""
    qs = ",".join(f"{m}{c}" for c, m in codes)
    raw = None
    for _ in range(3):
        try:
            out = subprocess.run(["curl", "-sS", "--max-time", "25",
                                  f"https://qt.gtimg.cn/q={qs}"],
                                 capture_output=True, timeout=35)
            if out.returncode == 0 and out.stdout:
                raw = out.stdout.decode("gbk", errors="ignore")
                break
        except Exception:
            pass
        time.sleep(1.5)
    result = {}
    if not raw:
        return result
    for line in raw.split(";"):
        if '="' not in line:
            continue
        f = line.split('="')[1].rstrip('";').split("~")
        if len(f) < 47:
            continue
        result[f[2]] = {
            "name": f[1] or None,
            "price": tof(f[3]),
            "pe_ttm": tof(f[39]),
            "pb": tof(f[46]),
            "ret1y": tof(f[79]) if len(f) > 79 else None,
        }
    return result


def _forecast_years(row):
    years = []
    for i in (1, 2, 3, 4):
        year = row.get(f"YEAR{i}")
        eps = tof(row.get(f"EPS{i}"))
        mark = row.get(f"YEAR_MARK{i}")
        if year in (None, "", "-"):
            continue
        try:
            year_i = int(year)
        except (TypeError, ValueError):
            continue
        years.append({"year": year_i, "eps": eps, "mark": mark})
    years.sort(key=lambda r: r["year"])
    return years


def fetch_forecast(codes):
    """东财一致预期 RPT_WEB_RESPREDICT: YEAR/EPS/YEAR_MARK + 机构数 + 评级。"""
    out = {}
    for code, _ in codes:
        u = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
             f"?reportName=RPT_WEB_RESPREDICT&columns=ALL&filter=(SECURITY_CODE%3D%22{code}%22)"
             "&pageNumber=1&pageSize=8&source=WEB&client=WEB")
        raw = curl(u)
        if not raw:
            out[code] = None
            continue
        try:
            d = json.loads(raw)
            data = (d.get("result") or {}).get("data") or []
            if not data:
                out[code] = None
            else:
                x = data[0]
                years = _forecast_years(x)
                by_year = {r["year"]: r for r in years}
                out[code] = {
                    "years": years,
                    "norg": x.get("RATING_ORG_NUM"),
                    "buy": x.get("RATING_BUY_NUM"),
                    "add": x.get("RATING_ADD_NUM"),
                    "year1": x.get("YEAR1"), "mark1": x.get("YEAR_MARK1"), "eps1": tof(x.get("EPS1")),
                    "year2": x.get("YEAR2"), "mark2": x.get("YEAR_MARK2"), "eps2": tof(x.get("EPS2")),
                    "year3": x.get("YEAR3"), "mark3": x.get("YEAR_MARK3"), "eps3": tof(x.get("EPS3")),
                    "year4": x.get("YEAR4"), "mark4": x.get("YEAR_MARK4"), "eps4": tof(x.get("EPS4")),
                    "eps25a": (by_year.get(2025) or {}).get("eps"),
                    "eps26e": (by_year.get(2026) or {}).get("eps"),
                    "eps27e": (by_year.get(2027) or {}).get("eps"),
                    "eps28e": (by_year.get(2028) or {}).get("eps"),
                }
        except Exception:
            out[code] = None
        time.sleep(0.3)
    return out


def _series(rows, key, cutoff):
    return [r[key] for r in rows
            if r.get("TRADE_DATE", "") >= cutoff
            and r.get(key) not in (None, "", "-")
            and r[key] > 0]


def percentile(series, curval):
    if not series or curval is None or curval <= 0:
        return None
    return round(sum(1 for v in series if v < curval) / len(series) * 100)


def fetch_hist(codes):
    """东财历史每日 PE_TTM/PB_MRQ。只用于分位,不覆盖腾讯现价。"""
    out = {}
    now = datetime.now().strftime("%Y-%m-%d")

    def cutoff(y):
        try:
            return str(int(now[:4]) - y) + now[4:]
        except Exception:
            return now

    for code, _ in codes:
        u = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
             "?reportName=RPT_VALUEANALYSIS_DET"
             "&columns=SECURITY_CODE,TRADE_DATE,CLOSE_PRICE,PE_TTM,PB_MRQ"
             f"&filter=(SECURITY_CODE%3D%22{code}%22)&pageNumber=1&pageSize=2000"
             "&sortTypes=-1&sortColumns=TRADE_DATE&source=WEB&client=WEB")
        raw = curl(u)
        rows = []
        if raw:
            try:
                d = json.loads(raw)
                rows = (d.get("result") or {}).get("data") or []
            except Exception:
                rows = []
        rows = sorted(rows, key=lambda r: r.get("TRADE_DATE", ""))
        if not rows:
            out[code] = None
            continue
        cur = rows[-1]
        c3, c5 = cutoff(3), cutoff(5)
        out[code] = {
            "last_price": cur.get("CLOSE_PRICE"),
            "last_pe": cur.get("PE_TTM"),
            "last_pb": cur.get("PB_MRQ"),
            "last_date": cur.get("TRADE_DATE"),
            "hist_days": len(rows),
            "pe3y": _series(rows, "PE_TTM", c3),
            "pb3y": _series(rows, "PB_MRQ", c3),
            "pe5y": _series(rows, "PE_TTM", c5) or _series(rows, "PE_TTM", "0000-00-00"),
            "pb5y": _series(rows, "PB_MRQ", c5) or _series(rows, "PB_MRQ", "0000-00-00"),
        }
        time.sleep(0.3)
    return out


def bucket(x, edges):
    if x is None:
        return None
    for i, e in enumerate(edges):
        if x < e:
            return i + 1
    return len(edges) + 1


def growth_score(rev_g, rev_cagr, nps_g, nps_flag=None):
    """缺项保持缺失并按可用项重归一化,不静默打成中性 3 分。"""
    flag = nps_flag or "normal"
    parts = []
    if rev_g is not None:
        parts.append((0.5, bucket(rev_g, [0, 15, 30, 50])))
    if rev_cagr is not None:
        parts.append((0.3, bucket(rev_cagr, [5, 15, 25, 40])))
    if flag == "turnaround_profit":
        parts.append((0.2, 5))
    elif flag == "still_loss":
        parts.append((0.2, 1))
    elif flag != "missing" and nps_g is not None:
        parts.append((0.2, bucket(nps_g, [0, 20, 50, 100])))
    if not parts:
        return None
    weight = sum(item[0] for item in parts)
    return round(sum(item[0] * item[1] for item in parts) / weight, 2)


def parse_rating_states(s, n, quality):
    if quality is None:
        if s is not None:
            sys.exit("未传 --quality 时不要传 --rating-state")
        return None
    if s is None:
        sys.exit("传入 --quality 时必须同时传 --rating-state(FORMAL 或 PROVISIONAL)")
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != n:
        sys.exit("--rating-state 数量必须与 --tickers 一致")
    out = []
    for i, raw in enumerate(parts):
        key = raw.replace("-", "_").upper()
        if key in {"NR", "N_R", "N/R"}:
            key = "N_R"
        if key in REJECTED_QUALITY_STATES or key not in ALLOWED_QUALITY_STATES:
            sys.exit(
                f"--quality[{i}] 来自 {raw or '空'}，诊断分不能进入三维综合分；"
                "仅 FORMAL/PROVISIONAL 可用"
            )
        if quality[i] is None:
            sys.exit(f"--quality[{i}] 为空，不能与评级状态一起使用")
        out.append(key)
    return out


def valuation_score(peg, ret1y, pb):
    def v_pb(x):
        if x is None:
            return 3
        return 5 if x <= 4 else 4 if x <= 8 else 3 if x <= 12 else 2 if x <= 20 else 1

    def v_overdraw(ret):
        if ret is None:
            return 3
        return 5 if ret <= 50 else 4 if ret <= 100 else 3 if ret <= 200 else 2 if ret <= 300 else 1

    def v_peg(x):
        if x is None:
            return 1
        return 5 if x <= 1 else 4 if x <= 2 else 3 if x <= 3 else 2 if x <= 5 else 1

    return round(0.4 * v_peg(peg) + 0.3 * v_overdraw(ret1y) + 0.3 * v_pb(pb), 2)


def compute_peg(pe, rev_g):
    """PEG = PE_TTM ÷ 营收增速%; PE<0/PE>500/增速≤0或>200% → 无意义。"""
    if pe is None or rev_g is None:
        return None
    if not (0 < pe <= 500 and 0 < rev_g <= 200):
        return None
    return round(pe / rev_g, 2)


def compute_fwd_peg(pe_fwd, eps_g):
    """fwd_peg = 前瞻PE ÷ EPS增速%; 无意义规则与营收 PEG 相同。"""
    if pe_fwd is None or eps_g is None:
        return None
    if not (0 < pe_fwd <= 500 and 0 < eps_g <= 200):
        return None
    return round(pe_fwd / eps_g, 2)


def pick_eps0(years):
    """EPS0: 最近一期为正的实际(A),否则最早一期为正的预测(E)。"""
    if not years:
        return None
    actuals = [r for r in years if r.get("mark") == "A" and r.get("eps") and r["eps"] > 0]
    if actuals:
        return actuals[-1]
    positives = [r for r in years if r.get("eps") and r["eps"] > 0]
    return positives[0] if positives else None


def fwd_growth(fc, price):
    """下一预测年相对 EPS0 的增速与前瞻 PE/PEG。"""
    if not fc:
        return None, None, None
    years = fc.get("years") or []
    base = pick_eps0(years)
    if not base:
        return None, None, None
    nxt = next((r for r in years if r["year"] == base["year"] + 1), None)
    if not nxt or not nxt.get("eps") or nxt["eps"] <= 0 or not base.get("eps") or base["eps"] <= 0:
        return None, None, None
    eps_g = round((nxt["eps"] / base["eps"] - 1) * 100, 1)
    pe_fwd = round(price / nxt["eps"], 2) if price and nxt["eps"] else None
    return eps_g, pe_fwd, compute_fwd_peg(pe_fwd, eps_g)


def dcf_5y(eps0, g, disc, g_term):
    """5年预测: 前3年增速g, 第4-5年衰减(g*0.7/g*0.5), 终值永续g_term。"""
    if eps0 is None or eps0 <= 0:
        return None
    if disc <= g_term:
        return None
    r = disc / 100.0
    gt = g_term / 100.0
    eps = [eps0 * (1 + g) ** t for t in (1, 2, 3)]
    eps.append(eps[-1] * (1 + g * 0.7))
    eps.append(eps[-1] * (1 + g * 0.5))
    v = sum(e / (1 + r) ** t for t, e in enumerate(eps, 1))
    tv = eps[-1] * (1 + gt) / (r - gt)
    v += tv / (1 + r) ** 5
    return v


def dcf_triple(fc, price, disc):
    """基于一致预期EPS的DCF三情景。返回 (悲观,基准,乐观,现价位置,g,eps0,eps0_year)。"""
    empty = (None, None, None, None, None, None, None)
    if not fc:
        return empty
    years = fc.get("years") or []
    base = pick_eps0(years)
    if not base:
        return empty
    later_pos = [r for r in years if r["year"] > base["year"] and r.get("eps") and r["eps"] > 0]
    if not later_pos:
        return empty
    later = next((r for r in later_pos if r["year"] == base["year"] + 3), later_pos[-1])
    n_years = later["year"] - base["year"]
    if n_years < 1 or not base.get("eps") or base["eps"] <= 0:
        return empty
    g = (later["eps"] / base["eps"]) ** (1 / n_years) - 1
    g = min(max(g, 0.03), 0.6)
    vb = dcf_5y(base["eps"], g * 0.4, disc, 2.0)
    vm = dcf_5y(base["eps"], g, disc, 3.0)
    vo = dcf_5y(base["eps"], g * 1.5, disc, 4.0)
    pos = None
    if price is not None and vb is not None and vm is not None and vo is not None:
        pos = ("低估" if price <= vb else "合理" if price <= vm
               else "偏贵" if price <= vo else "高估")
    round3 = lambda x: None if x is None else round(x, 2)
    return round3(vb), round3(vm), round3(vo), pos, round(g, 4), round(base["eps"], 6), base["year"]


def at(seq, i):
    return None if seq is None else seq[i]


def main():
    ap = argparse.ArgumentParser(description="半导体估值工具")
    ap.add_argument("--tickers", required=True, help="证券代码,逗号分隔,如 688019.SH,002371.SZ")
    ap.add_argument("--quality", default=None, help="基本面分(0-5),逗号分隔,与tickers对应;仅FORMAL/PROVISIONAL")
    ap.add_argument(
        "--rating-state", dest="rating_state", default=None,
        help="与 --quality 对应的 jibenmian-pingfen rating_state,仅 FORMAL 或 PROVISIONAL",
    )
    ap.add_argument("--growth", default=None, help="增长分(0-5),可选")
    ap.add_argument("--rev-g", dest="rev_g", default=None, help="营收增速%,逗号分隔")
    ap.add_argument("--rev-cagr", dest="rev_cagr", default=None, help="三年营收CAGR%,逗号分隔")
    ap.add_argument("--nps-g", dest="nps_g", default=None, help="扣非增速%,逗号分隔")
    ap.add_argument("--nps-flag", dest="nps_flag", default=None,
                    help="扣非状态 normal|turnaround_profit|still_loss|missing,逗号分隔")
    ap.add_argument("--risk", default="balanced", choices=list(RISK.keys()))
    ap.add_argument("--out-dir", default=".", help="输出目录")
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        sys.exit("--tickers 不能为空")
    try:
        codes = [parse_ticker(t) for t in tickers]
    except ValueError as e:
        sys.exit(str(e))

    n = len(tickers)
    quality = parse_optional_floats(args.quality, n, "--quality")
    rating_states = parse_rating_states(args.rating_state, n, quality)
    growth_in = parse_optional_floats(args.growth, n, "--growth")
    rev_g_in = parse_optional_floats(args.rev_g, n, "--rev-g")
    rev_cagr_in = parse_optional_floats(args.rev_cagr, n, "--rev-cagr")
    nps_g_in = parse_optional_floats(args.nps_g, n, "--nps-g")
    nps_flag_in = parse_optional_flags(args.nps_flag, n, "--nps-flag", NPS_FLAGS)
    rk = RISK[args.risk]
    os.makedirs(args.out_dir, exist_ok=True)

    print("拉取行情...")
    market = fetch_market(codes)
    print("拉取一致预期...")
    forecast = fetch_forecast(codes)
    print("拉取历史分位...")
    hist = fetch_hist(codes)

    rows = []
    for i, (code, mkt) in enumerate(codes):
        m = market.get(code) or {}
        fc = forecast.get(code)
        h = hist.get(code)
        price, pe, pb, ret = m.get("price"), m.get("pe_ttm"), m.get("pb"), m.get("ret1y")
        price_source = "tencent" if price is not None else None
        if price is None and h and h.get("last_price") is not None:
            price = h.get("last_price")
            pe = pe if pe is not None else h.get("last_pe")
            pb = pb if pb is not None else h.get("last_pb")
            price_source = "eastmoney_hist_fallback"
        pe_for_pct = pe if pe is not None else (h or {}).get("last_pe")
        pb_for_pct = pb if pb is not None else (h or {}).get("last_pb")

        q = at(quality, i)
        rev_g = at(rev_g_in, i)
        peg = compute_peg(pe, rev_g)
        eps_g, pe_fwd, fwd_peg = fwd_growth(fc, price)
        vb, vm, vo, pos, dcf_g, eps0, eps0_year = dcf_triple(fc, price, rk["disc"])

        growth_g = at(growth_in, i)
        if growth_g is None:
            growth_g = growth_score(rev_g, at(rev_cagr_in, i), at(nps_g_in, i), at(nps_flag_in, i))
        val = valuation_score(peg, ret, pb)
        total = None
        if q is not None and growth_g is not None:
            total = round(0.5 * q + 0.3 * growth_g + 0.2 * val, 2)

        rows.append({
            "ticker": tickers[i], "code": code, "market": mkt.upper(),
            "name": m.get("name"),
            "price": price, "price_source": price_source,
            "pe_ttm": pe, "pb": pb, "ret1y": ret,
            "pe3y_pct": percentile((h or {}).get("pe3y") or [], pe_for_pct),
            "pb3y_pct": percentile((h or {}).get("pb3y") or [], pb_for_pct),
            "pe5y_pct": percentile((h or {}).get("pe5y") or [], pe_for_pct),
            "pb5y_pct": percentile((h or {}).get("pb5y") or [], pb_for_pct),
            "hist_days": (h or {}).get("hist_days"),
            "hist_last_date": (h or {}).get("last_date"),
            "year1": (fc or {}).get("year1"), "mark1": (fc or {}).get("mark1"), "eps1": (fc or {}).get("eps1"),
            "year2": (fc or {}).get("year2"), "mark2": (fc or {}).get("mark2"), "eps2": (fc or {}).get("eps2"),
            "year3": (fc or {}).get("year3"), "mark3": (fc or {}).get("mark3"), "eps3": (fc or {}).get("eps3"),
            "year4": (fc or {}).get("year4"), "mark4": (fc or {}).get("mark4"), "eps4": (fc or {}).get("eps4"),
            "eps25a": (fc or {}).get("eps25a"), "eps26e": (fc or {}).get("eps26e"),
            "eps27e": (fc or {}).get("eps27e"), "eps28e": (fc or {}).get("eps28e"),
            "norg": (fc or {}).get("norg"), "buy": (fc or {}).get("buy"), "add": (fc or {}).get("add"),
            "rev_g": rev_g, "peg": peg,
            "fwd_eps_growth": eps_g, "fwd_pe": pe_fwd, "fwd_peg": fwd_peg,
            "dcf_bear": vb, "dcf_base": vm, "dcf_bull": vo, "dcf_position": pos,
            "dcf_g": dcf_g, "dcf_eps0": eps0, "dcf_eps0_year": eps0_year,
            "quality": q, "rating_state": at(rating_states, i),
            "growth": growth_g, "valuation_score": val,
            "total_score": total,
            "risk": args.risk, "disc_rate": rk["disc"],
        })
        print(f"{tickers[i]}: price={price}({price_source}) PE={pe} PB={pb} 1Y={ret} "
              f"PE5y%={rows[-1]['pe5y_pct']} PB5y%={rows[-1]['pb5y_pct']} "
              f"PEG={peg} fwdPEG={fwd_peg} DCF[{vb}/{vm}/{vo}]={pos} 综合={total}")

    rows.sort(key=lambda r: (r["total_score"] is None, -(r["total_score"] or 0), r["ticker"]))
    with open(os.path.join(args.out_dir, "valuation_output.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out_dir, "valuation_output.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"\n输出已写入 {args.out_dir}/valuation_output.csv 和 .json")


if __name__ == "__main__":
    main()
