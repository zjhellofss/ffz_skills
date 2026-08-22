#!/usr/bin/env python3
"""从本地结构化数据事实快照生成 ROE 杜邦三因子对账表。"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_DIR = SCRIPT_DIR.parents[1] / "jibenmian-pingfen" / "scripts"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from score import (  # noqa: E402
    D,
    fact_value,
    load_facts,
    run_fact_validator,
    sha256_file,
)


SCHEMA_VERSION = "1.0"
Q_RATIO = D("0.0001")
Q_PERCENT = D("0.01")
ZERO = D("0")

INPUT_FIELDS = [
    "company", "entity_id", "fy", "scope",
    "revenue_fact_id", "net_profit_parent_fact_id", "net_profit_total_fact_id",
    "total_assets_open_fact_id", "total_assets_close_fact_id",
    "parent_equity_open_fact_id", "parent_equity_close_fact_id",
    "total_equity_open_fact_id", "total_equity_close_fact_id",
    "disclosed_roe_fact_id", "notes",
]

FACT_METRICS = {
    "revenue_fact_id": "revenue",
    "net_profit_parent_fact_id": "net_profit_parent",
    "net_profit_total_fact_id": "net_profit_total",
    "total_assets_open_fact_id": "total_assets",
    "total_assets_close_fact_id": "total_assets",
    "parent_equity_open_fact_id": "equity_parent",
    "parent_equity_close_fact_id": "equity_parent",
    "total_equity_open_fact_id": "equity_total",
    "total_equity_close_fact_id": "equity_total",
    "disclosed_roe_fact_id": "roe_weighted_parent",
}

OUTPUT_FIELDS = [
    "company", "entity_id", "fy", "scope", "status",
    "parent_net_margin_pct", "asset_turnover", "parent_equity_multiplier",
    "dupont_parent_roe_pct", "disclosed_weighted_parent_roe_pct",
    "reconciliation_delta_pct", "reconciliation_status",
    "total_equity_multiplier", "total_equity_roe_pct",
    "average_nci_equity", "nci_share_of_total_equity_pct",
    "parent_multiplier_amplification_pct", "major_nci_flag",
    "group_loss_parent_profit_flag", "fact_ids", "notes",
]


def cell(row: dict[str | None, str | None], key: str) -> str:
    value = row.get(key, "")
    return "" if value is None else str(value).strip()


def quantize(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def text(value: Decimal | None, quantum: Decimal | None = None) -> str:
    if value is None:
        return ""
    if quantum is not None:
        value = quantize(value, quantum)
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def read_mapping(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        duplicates = sorted(name for name, count in Counter(fields).items() if count > 1)
        if duplicates:
            raise ValueError(f"杜邦输入存在重复表头: {','.join(duplicates)}")
        missing = set(INPUT_FIELDS) - set(fields)
        if missing:
            raise ValueError(f"杜邦输入缺少列: {','.join(sorted(missing))}")
        rows = [{field: cell(row, field) for field in INPUT_FIELDS} for row in reader]
    if not rows:
        raise ValueError("杜邦输入没有数据行")
    seen: set[tuple[str, str]] = set()
    for line_no, row in enumerate(rows, start=2):
        for field in INPUT_FIELDS[:-1]:
            if not row[field]:
                raise ValueError(f"杜邦输入第{line_no}行: {field}为空")
        if not row["fy"].startswith("FY") or not row["fy"][2:].isdigit():
            raise ValueError(f"杜邦输入第{line_no}行: fy应为FY2025形式")
        key = (row["entity_id"], row["fy"])
        if key in seen:
            raise ValueError(f"杜邦输入第{line_no}行: entity_id+fy重复")
        seen.add(key)
    return rows


def verify_fact_set(row: dict[str, str], facts: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    units: set[str] = set()
    currencies: set[str] = set()
    current_year = int(row["fy"][2:])
    for field, expected_metric in FACT_METRICS.items():
        fact_id = row[field]
        if fact_id not in facts:
            raise ValueError(f"{row['entity_id']}: 不存在fact_id={fact_id}")
        fact = facts[fact_id]
        if fact["company"] != row["company"]:
            raise ValueError(f"{row['entity_id']}: fact_id={fact_id}属于其他公司")
        if fact["metric"] != expected_metric:
            raise ValueError(
                f"{row['entity_id']}: {field}要求metric={expected_metric}，实际为{fact['metric']}"
            )
        if fact["scope"] != row["scope"]:
            raise ValueError(f"{row['entity_id']}: fact_id={fact_id}的scope不一致")
        if fact["audit_status"] != "audited":
            raise ValueError(f"{row['entity_id']}: fact_id={fact_id}不是audited")
        fact_value(fact, fact_id)
        selected[field] = fact
        if field != "disclosed_roe_fact_id":
            units.add(fact["unit"])
            currencies.add(fact["currency"])

        period = fact["period"]
        if field in {"revenue_fact_id", "net_profit_parent_fact_id", "net_profit_total_fact_id", "disclosed_roe_fact_id"}:
            if period != row["fy"]:
                raise ValueError(f"{row['entity_id']}: fact_id={fact_id}不是当前FY流量")
        elif field.endswith("_open_fact_id") and not period.startswith(str(current_year - 1)):
            raise ValueError(f"{row['entity_id']}: fact_id={fact_id}不是期初时点")
        elif field.endswith("_close_fact_id") and not period.startswith(str(current_year)):
            raise ValueError(f"{row['entity_id']}: fact_id={fact_id}不是期末时点")

    if len(units) != 1 or len(currencies) != 1:
        raise ValueError(f"{row['entity_id']}: 金额事实的unit/currency不一致")
    roe_fact = selected["disclosed_roe_fact_id"]
    if roe_fact["unit"] != "percent" or roe_fact["attribution"] != "parent":
        raise ValueError(f"{row['entity_id']}: 披露ROE必须为percent、parent归属")
    if selected["net_profit_parent_fact_id"]["attribution"] != "parent":
        raise ValueError(f"{row['entity_id']}: 归母净利润归属必须为parent")
    if selected["net_profit_total_fact_id"]["attribution"] != "total":
        raise ValueError(f"{row['entity_id']}: 合并净利润归属必须为total")
    return selected


def calculate(row: dict[str, str], selected: dict[str, dict[str, str]]) -> dict[str, str]:
    value = lambda field: fact_value(selected[field], row[field])
    revenue = value("revenue_fact_id")
    parent_profit = value("net_profit_parent_fact_id")
    total_profit = value("net_profit_total_fact_id")
    assets_open = value("total_assets_open_fact_id")
    assets_close = value("total_assets_close_fact_id")
    parent_equity_open = value("parent_equity_open_fact_id")
    parent_equity_close = value("parent_equity_close_fact_id")
    total_equity_open = value("total_equity_open_fact_id")
    total_equity_close = value("total_equity_close_fact_id")
    disclosed_roe = value("disclosed_roe_fact_id")

    average_assets = (assets_open + assets_close) / D("2")
    average_parent_equity = (parent_equity_open + parent_equity_close) / D("2")
    average_total_equity = (total_equity_open + total_equity_close) / D("2")
    if revenue == ZERO or average_assets <= ZERO or average_parent_equity <= ZERO or average_total_equity <= ZERO:
        return {
            "company": row["company"], "entity_id": row["entity_id"],
            "fy": row["fy"], "scope": row["scope"],
            "status": "N/M_NONPOSITIVE_DENOMINATOR",
            "fact_ids": ";".join(row[field] for field in FACT_METRICS),
            "notes": row["notes"],
        }

    parent_net_margin = parent_profit / revenue
    asset_turnover = revenue / average_assets
    parent_multiplier = average_assets / average_parent_equity
    dupont_roe = parent_net_margin * asset_turnover * parent_multiplier * D("100")
    delta = dupont_roe - disclosed_roe
    total_multiplier = average_assets / average_total_equity
    total_equity_roe = total_profit / average_total_equity * D("100")
    average_nci = average_total_equity - average_parent_equity
    nci_share = average_nci / average_total_equity * D("100")
    amplification = (parent_multiplier / total_multiplier - D("1")) * D("100")
    major_nci = abs(nci_share) >= D("20")
    group_loss_parent_profit = total_profit < ZERO < parent_profit
    reconciliation = "matched" if abs(delta) <= D("1.00") else ("review" if abs(delta) <= D("2.00") else "explain")

    return {
        "company": row["company"],
        "entity_id": row["entity_id"],
        "fy": row["fy"],
        "scope": row["scope"],
        "status": "OK",
        "parent_net_margin_pct": text(parent_net_margin * D("100"), Q_PERCENT),
        "asset_turnover": text(asset_turnover, Q_RATIO),
        "parent_equity_multiplier": text(parent_multiplier, Q_RATIO),
        "dupont_parent_roe_pct": text(dupont_roe, Q_PERCENT),
        "disclosed_weighted_parent_roe_pct": text(disclosed_roe, Q_PERCENT),
        "reconciliation_delta_pct": text(delta, Q_PERCENT),
        "reconciliation_status": reconciliation,
        "total_equity_multiplier": text(total_multiplier, Q_RATIO),
        "total_equity_roe_pct": text(total_equity_roe, Q_PERCENT),
        "average_nci_equity": text(average_nci),
        "nci_share_of_total_equity_pct": text(nci_share, Q_PERCENT),
        "parent_multiplier_amplification_pct": text(amplification, Q_PERCENT),
        "major_nci_flag": str(major_nci).lower(),
        "group_loss_parent_profit_flag": str(group_loss_parent_profit).lower(),
        "fact_ids": ";".join(row[field] for field in FACT_METRICS),
        "notes": row["notes"],
    }


def write_outputs(
    out_dir: Path,
    mapping_path: Path,
    facts_path: Path,
    source_root: Path | None,
    rows: list[dict[str, str]],
    validation: dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "dupont.csv"
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    shutil.copyfile(mapping_path, out_dir / "dupont_inputs.snapshot.csv")
    shutil.copyfile(facts_path, out_dir / "facts.snapshot.csv")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rounding": "Decimal ROUND_HALF_UP",
        "major_nci_threshold_pct": "20",
        "reconciliation_thresholds_pct": {"matched": "<=1.00", "review": "<=2.00", "explain": ">2.00"},
        "input": {"path": str(mapping_path.resolve()), "sha256": sha256_file(mapping_path)},
        "facts": {"path": str(facts_path.resolve()), "sha256": sha256_file(facts_path), "source_root": str(source_root.resolve()) if source_root else "", "validation": validation},
        "output": {"path": output_path.name, "sha256": sha256_file(output_path)},
        "entity_count": len(rows),
    }
    (out_dir / "dupont_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="杜邦fact-ID映射CSV")
    parser.add_argument("--facts", type=Path, required=True, help="本地结构化数据事实快照")
    parser.add_argument("--source-root", type=Path, required=True, help="本地数据集根目录")
    parser.add_argument("--out-dir", type=Path, required=True, help="输出目录")
    return parser


def run(args: argparse.Namespace) -> list[dict[str, str]]:
    if not args.input.exists() or not args.facts.exists():
        raise ValueError("输入映射或facts.csv不存在")
    validation = run_fact_validator(args.facts, args.source_root, False, "local")
    facts = load_facts(args.facts)
    mappings = read_mapping(args.input)
    rows = [calculate(row, verify_fact_set(row, facts)) for row in mappings]
    write_outputs(args.out_dir, args.input, args.facts, args.source_root, rows, validation)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = run(args)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for row in rows:
        print(
            f"{row['entity_id']} {row['fy']} ROE={row.get('dupont_parent_roe_pct', '-')}% "
            f"披露={row.get('disclosed_weighted_parent_roe_pct', '-')}% "
            f"对账={row.get('reconciliation_status', row['status'])}"
        )
    print(f"输出已写入 {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
