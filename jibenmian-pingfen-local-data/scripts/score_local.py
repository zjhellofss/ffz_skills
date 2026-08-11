#!/usr/bin/env python3
"""Read /home/fss/data directly, prepare evidence, and run strict scoring."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_data import add_common_arguments, prepare_local_inputs  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser)
    parser.add_argument(
        "--with-dupont",
        action="store_true",
        help="同时生成ROE杜邦分解（仅完整FY）",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def run_command(command: list[str]) -> None:
    process = subprocess.run(command, check=False)
    if process.returncode:
        raise RuntimeError(f"命令失败(exit={process.returncode}): {' '.join(command)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.with_dupont and args.period:
        parser.error("季度诊断暂不支持--with-dupont；请删除该参数")
    try:
        paths = prepare_local_inputs(args)
    except ValueError as exc:
        parser.error(str(exc))
    score_command = [
        sys.executable,
        str(SCRIPT_DIR / "score.py"),
        str(paths["score_input"]),
        "--mode", "strict",
        "--facts", str(paths["facts"]),
        "--source-root", str(paths["source_root"]),
        "--out-dir", str(args.out_dir),
    ]
    if args.quiet:
        score_command.append("--quiet")
    run_command(score_command)

    if args.with_dupont:
        dupont_input = paths["dupont_input"]
        if not dupont_input:
            raise ValueError("本地数据不足以生成完整杜邦fact-ID映射")
        run_command([
            sys.executable,
            str(SCRIPT_DIR / "dupont.py"),
            str(dupont_input),
            "--facts", str(paths["facts"]),
            "--source-root", str(paths["source_root"]),
            "--out-dir", str(args.out_dir / "dupont"),
        ])
    print(f"output={args.out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
