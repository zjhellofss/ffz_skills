#!/usr/bin/env python3
"""批量读取本地 CSV，合并同一 peer_group 后调用共享评分引擎。"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_data import (  # noqa: E402
    add_common_arguments,
    prepare_local_inputs,
    resolve_dataset_root,
)


FACT_FIELDS = [
    "fact_id", "company", "metric", "period", "period_type", "scope",
    "attribution", "value", "unit", "currency", "status", "audit_status",
    "source_file", "locator_type", "locator", "source_line_item", "formula",
    "input_fact_ids", "notes",
]


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        return fields, list(reader)


def _write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument(
        "--tickers",
        required=True,
        help="证券代码逗号分隔，如 688981.SH,002371.SZ",
    )
    parser.add_argument(
        "--companies",
        help="公司名逗号分隔，顺序与 --tickers 对应；缺省时用代码",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tickers = [item.strip().upper() for item in args.tickers.split(",") if item.strip()]
    if not tickers:
        parser.error("--tickers 不能为空")
    companies = (
        [item.strip() for item in args.companies.split(",")]
        if args.companies else [""] * len(tickers)
    )
    if len(companies) != len(tickers):
        parser.error("--companies 数量必须与 --tickers 一致")

    staging = args.out_dir / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    fact_rows: list[dict[str, str]] = []
    score_rows: list[dict[str, str]] = []
    score_fields: list[str] = []
    manifests = []
    peer_group = args.peer_group or f"{args.subsector}-cn-a"

    for ticker, company in zip(tickers, companies):
        item_args = argparse.Namespace(**vars(args))
        item_args.ticker = ticker
        item_args.company = company or None
        item_args.peer_group = peer_group
        item_args.entity_id = ticker
        item_args.out_dir = staging / ticker.replace(".", "-")
        paths = prepare_local_inputs(item_args)
        _, facts = _read_rows(paths["facts"])
        fields, scores = _read_rows(paths["score_input"])
        fact_rows.extend(facts)
        score_rows.extend(scores)
        score_fields = fields
        manifests.append({
            "ticker": ticker,
            "company": company or ticker,
            "facts": str(paths["facts"]),
            "score_input": str(paths["score_input"]),
        })

    combined_facts = args.out_dir / "local-facts.csv"
    combined_scores = args.out_dir / "score-input.csv"
    _write_rows(combined_facts, FACT_FIELDS, fact_rows)
    _write_rows(combined_scores, score_fields, score_rows)
    (args.out_dir / "cohort-manifest.json").write_text(
        json.dumps(
            {
                "peer_group": peer_group,
                "subsector": args.subsector,
                "tickers": tickers,
                "members": manifests,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(SCRIPT_DIR / "score.py"),
        str(combined_scores),
        "--mode", "strict",
        "--facts", str(combined_facts),
        "--source-root", str(resolve_dataset_root(args.data_root)),
        "--evidence-validator", "local",
        "--out-dir", str(args.out_dir),
    ]
    if args.quiet:
        command.append("--quiet")
    process = subprocess.run(command, check=False)
    if process.returncode:
        return process.returncode
    print(f"cohort_output={args.out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
