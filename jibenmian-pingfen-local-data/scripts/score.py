#!/usr/bin/env python3
"""本地结构化数据评分入口：调用 jibenmian-pingfen 共享引擎，证据校验走 local CSV。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


SHARED = Path(__file__).resolve().parents[2] / "jibenmian-pingfen" / "scripts" / "score.py"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--evidence-validator" not in args:
        args.extend(["--evidence-validator", "local"])
    sys.argv = [str(SHARED), *args]
    try:
        runpy.run_path(str(SHARED), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else int(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
