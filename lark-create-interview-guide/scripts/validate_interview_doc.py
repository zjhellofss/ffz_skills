#!/usr/bin/env python3
"""Validate a Feishu interview-guide document produced by this skill."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


FORBIDDEN_ANSWER_PATTERNS = (
    (
        "source-document in-clause self-reference",
        re.compile("原文" + "中"),
    ),
    (
        "source-document as subject self-reference",
        re.compile("原文" + r"把"),
    ),
    (
        "unspecified present-time vLLM prefix",
        re.compile("当前" + r"\s*" + "vllm", re.IGNORECASE),
    ),
)


def fetch_xml(doc: str) -> str:
    command = [
        "lark-cli",
        "docs",
        "+fetch",
        "--doc",
        doc,
        "--detail",
        "with-ids",
        "--scope",
        "full",
        "-q",
        ".data.document.content",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"failed to fetch {doc}: {message}")
    return result.stdout.strip()


def parse_fragment(content: str) -> ET.Element:
    try:
        return ET.fromstring(f"<root>{content}</root>")
    except ET.ParseError as exc:
        raise RuntimeError(f"document XML is not parseable: {exc}") from exc


def text_of(element: ET.Element) -> str:
    return "".join(element.itertext())


def hrefs_of(element: ET.Element) -> list[str]:
    return [node.attrib["href"] for node in element.iter("a") if "href" in node.attrib]


def validate(
    target_root: ET.Element,
    expected_questions: int | None,
    source_ids: set[str] | None,
    max_single_answer_chars: int = 180,
) -> dict[str, object]:
    children = list(target_root)
    question_positions = [i for i, child in enumerate(children) if child.tag == "h3"]
    issues: list[str] = []
    question_rows: list[dict[str, object]] = []

    seen_questions: set[str] = set()
    for ordinal, start in enumerate(question_positions, start=1):
        heading = text_of(children[start]).strip()
        if heading in seen_questions:
            issues.append(f"duplicate question heading: {heading}")
        seen_questions.add(heading)

        end = len(children)
        for cursor in range(start + 1, len(children)):
            if children[cursor].tag in {"h2", "h3"}:
                end = cursor
                break
        region = children[start + 1 : end]
        answer_blocks = [
            block for block in region if block.tag == "p" and "面试回答：" in text_of(block)
        ]
        source_blocks = [
            block for block in region if block.tag == "p" and "原文定位" in text_of(block)
        ]

        answer_paragraphs: list[ET.Element] = []
        answer_chars = 0
        forbidden_wording: list[str] = []
        if len(answer_blocks) == 1:
            answer_start = region.index(answer_blocks[0])
            answer_end = len(region)
            if source_blocks:
                source_start = region.index(source_blocks[0])
                if source_start <= answer_start:
                    issues.append(
                        f"question {ordinal} source block appears before answer: {heading}"
                    )
                else:
                    answer_end = source_start
            answer_paragraphs = [
                block
                for block in region[answer_start:answer_end]
                if block.tag == "p" and text_of(block).strip()
            ]
            answer_text = "".join(text_of(block) for block in answer_paragraphs)
            answer_text = answer_text.replace("面试回答：", "", 1)
            answer_chars = len(re.sub(r"\s+", "", answer_text))
            for label, pattern in FORBIDDEN_ANSWER_PATTERNS:
                if pattern.search(answer_text):
                    forbidden_wording.append(label)
                    issues.append(
                        f"question {ordinal} contains forbidden answer wording "
                        f"({label}): {heading}"
                    )
            if (
                max_single_answer_chars > 0
                and answer_chars > max_single_answer_chars
                and len(answer_paragraphs) < 2
            ):
                issues.append(
                    f"question {ordinal} answer is {answer_chars} chars but has only "
                    f"{len(answer_paragraphs)} paragraph; split it into semantic paragraphs: "
                    f"{heading}"
                )

        if len(answer_blocks) != 1:
            issues.append(
                f"question {ordinal} has {len(answer_blocks)} answer blocks: {heading}"
            )
        if len(source_blocks) != 1:
            issues.append(
                f"question {ordinal} has {len(source_blocks)} source blocks: {heading}"
            )

        source_href = ""
        if source_blocks:
            hrefs = hrefs_of(source_blocks[0])
            if not hrefs:
                issues.append(f"question {ordinal} source block has no link: {heading}")
            else:
                source_href = hrefs[0]
                fragment = urlparse(source_href).fragment
                if not fragment:
                    issues.append(f"question {ordinal} source link has no fragment: {heading}")
                elif source_ids is not None and fragment not in source_ids:
                    issues.append(
                        f"question {ordinal} source fragment not found: {fragment}"
                    )

        question_rows.append(
            {
                "ordinal": ordinal,
                "heading": heading,
                "answer_blocks": len(answer_blocks),
                "answer_paragraphs": len(answer_paragraphs),
                "answer_chars": answer_chars,
                "forbidden_wording": forbidden_wording,
                "source_blocks": len(source_blocks),
                "source_href": source_href,
            }
        )

    if expected_questions is not None and len(question_positions) != expected_questions:
        issues.append(
            f"expected {expected_questions} questions, found {len(question_positions)}"
        )

    full_text = text_of(target_root)
    if re.search(r"\bldots\b", full_text):
        issues.append("found malformed LaTeX token 'ldots'")

    answer_count = full_text.count("面试回答：")
    if answer_count != len(question_positions):
        issues.append(
            f"answer label count {answer_count} does not match questions {len(question_positions)}"
        )

    linked_questions = sum(1 for row in question_rows if row["source_href"])
    return {
        "ok": not issues,
        "question_count": len(question_positions),
        "answer_count": answer_count,
        "linked_question_count": linked_questions,
        "issues": issues,
        "questions": question_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate question/answer/source-link alignment in a Feishu interview guide."
    )
    parser.add_argument("--doc", required=True, help="Output Feishu document URL or token")
    parser.add_argument(
        "--source-doc",
        help="Optional source Feishu document URL or token; validates link fragments",
    )
    parser.add_argument("--expected-questions", type=int)
    parser.add_argument(
        "--max-single-answer-chars",
        type=int,
        default=180,
        help=(
            "Fail when a single-paragraph answer exceeds this many non-whitespace "
            "characters; use 0 to disable (default: 180)"
        ),
    )
    args = parser.parse_args()

    try:
        target_root = parse_fragment(fetch_xml(args.doc))
        source_ids = None
        if args.source_doc:
            source_root = parse_fragment(fetch_xml(args.source_doc))
            source_ids = {
                element.attrib["id"]
                for element in source_root.iter()
                if "id" in element.attrib
            }
        report = validate(
            target_root,
            args.expected_questions,
            source_ids,
            args.max_single_answer_chars,
        )
    except RuntimeError as exc:
        report = {"ok": False, "issues": [str(exc)]}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
