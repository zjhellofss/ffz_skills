#!/usr/bin/env python3
"""Validate and render traceable financial charts from long-form CSV data.

Preferred chart columns:
chart_id,title,fact_id,display_label,render,axis,period_order,missing_policy

Use ``--facts facts.csv`` to populate and verify period, value, unit, currency,
and source from the caiwu-fenxi fact ledger. ``render`` must be ``bar``, ``line``,
or ``stacked_bar``; ``axis`` must be ``primary`` or ``secondary``.

Legacy columns remain supported in non-strict mode:
chart_id,title,kind,period,metric,value,unit,source

Legacy row-level ``bar``/``line`` mixtures are honored. Ambiguous ``bar_line``
is rejected instead of guessed. Missing values remain gaps and are never filled
with zero. The script writes PNG files, normalized per-chart CSV files,
``chart_manifest.json``, and ``captions.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.font_manager as font_manager
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing chart dependency. Install matplotlib, numpy, and pandas. "
        f"Original error: {exc}"
    ) from exc


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str


def _slug(text: str) -> str:
    value = re.sub(r"[^\w\u3400-\u9fff]+", "-", text.strip().lower(), flags=re.UNICODE)
    return value.strip("-") or "chart"


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def _configure_font(text: str, issues: list[Issue]) -> None:
    if not _contains_cjk(text):
        return
    installed = {font.name for font in font_manager.fontManager.ttflist}
    preferred = [
        "Noto Sans SC",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
    ]
    selected = next((name for name in preferred if name in installed), None)
    if selected:
        plt.rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
    else:
        issues.append(
            Issue(
                "WARN",
                "CJK_FONT_NOT_FOUND",
                "Chinese text is present but no known CJK font was found; glyphs may be missing",
            )
        )


def _is_ratio(metric: str, unit: str) -> bool:
    text = f"{metric} {unit}".lower()
    return any(
        token in text
        for token in [
            "margin",
            "ratio",
            "rate",
            "growth",
            "%",
            "percent",
            "毛利率",
            "净利率",
            "利润率",
            "占比",
            "比率",
            "增速",
            "增长率",
            "周转率",
        ]
    )


def _load_facts(path: Path) -> tuple[dict[str, dict[str, str]], list[Issue]]:
    issues: list[Issue] = []
    facts: dict[str, dict[str, str]] = {}
    required = {
        "fact_id",
        "metric",
        "period",
        "value",
        "unit",
        "currency",
        "status",
        "source_file",
        "locator_type",
        "locator",
    }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            if len(fieldnames) != len(set(fieldnames)):
                duplicates = sorted(
                    {name for name in fieldnames if fieldnames.count(name) > 1}
                )
                return {}, [
                    Issue(
                        "ERROR",
                        "FACTS_DUPLICATE_COLUMNS",
                        f"Facts CSV has duplicate columns: {', '.join(duplicates)}",
                    )
                ]
            missing = required - set(reader.fieldnames or [])
            if missing:
                return {}, [Issue("ERROR", "FACTS_SCHEMA", f"Facts CSV missing: {', '.join(sorted(missing))}")]
            for row_number, raw in enumerate(reader, start=2):
                if None in raw:
                    issues.append(
                        Issue(
                            "ERROR",
                            "MALFORMED_FACTS_ROW",
                            f"Facts row {row_number} has more fields than the header",
                        )
                    )
                    continue
                row = {
                    key: (raw.get(key) or "").strip()
                    for key in (reader.fieldnames or [])
                }
                fact_id = row["fact_id"]
                if not fact_id:
                    issues.append(Issue("ERROR", "EMPTY_FACT_ID", f"Facts row {row_number} has no fact_id"))
                elif fact_id in facts:
                    issues.append(Issue("ERROR", "DUPLICATE_FACT_ID", f"Duplicate fact_id {fact_id!r}"))
                else:
                    facts[fact_id] = row
    except OSError as exc:
        issues.append(Issue("ERROR", "FACTS_READ_FAILED", str(exc)))
    return facts, issues


def _load_chart_csv(path: Path) -> tuple[pd.DataFrame | None, list[Issue]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            if len(header) != len(set(header)):
                duplicates = sorted({name for name in header if header.count(name) > 1})
                return None, [
                    Issue(
                        "ERROR",
                        "CHART_DUPLICATE_COLUMNS",
                        f"Chart CSV has duplicate columns: {', '.join(duplicates)}",
                    )
                ]
            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    return None, [
                        Issue(
                            "ERROR",
                            "CHART_MALFORMED_ROW",
                            f"Chart row {row_number} has {len(row)} fields; header has {len(header)}",
                        )
                    ]
    except (OSError, csv.Error) as exc:
        return None, [Issue("ERROR", "CHART_READ_FAILED", str(exc))]
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:
        return None, [Issue("ERROR", "CHART_READ_FAILED", str(exc))]
    required = {"chart_id", "title"}
    missing = required - set(frame.columns)
    if missing:
        return None, [Issue("ERROR", "CHART_SCHEMA", f"Chart CSV missing: {', '.join(sorted(missing))}")]
    if frame.empty:
        return None, [Issue("ERROR", "EMPTY_CHART_DATA", "Chart CSV has no rows")]
    return frame.fillna(""), []


def _hydrate_from_facts(
    frame: pd.DataFrame, facts: dict[str, dict[str, str]] | None, strict: bool
) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    data = frame.copy()
    for column in (
        "fact_id",
        "display_label",
        "metric_code",
        "metric",
        "period",
        "value",
        "unit",
        "currency",
        "source",
        "render",
        "axis",
        "period_order",
        "missing_policy",
        "kind",
    ):
        if column not in data.columns:
            data[column] = ""

    if facts is None:
        if strict:
            issues.append(
                Issue("ERROR", "STRICT_REQUIRES_FACT_LEDGER", "Strict mode requires --facts with a validated ledger")
            )
        required = {"period", "metric", "value", "unit", "source"}
        missing = [column for column in required if not data[column].astype(str).str.strip().all()]
        if missing:
            issues.append(
                Issue("ERROR", "LEGACY_FIELDS_MISSING", f"Rows have blank legacy fields: {', '.join(sorted(missing))}")
            )
        if not data["fact_id"].astype(str).str.strip().all():
            issues.append(
                Issue(
                    "WARN",
                    "UNVERIFIED_CHART_VALUES",
                    "Chart rows are not linked to a facts ledger; values cannot be cross-checked",
                )
            )
        return data, issues

    if not data["fact_id"].astype(str).str.strip().all():
        issues.append(Issue("ERROR", "MISSING_FACT_LINK", "Every chart row must contain fact_id when --facts is used"))
        return data, issues

    hydrated_rows: list[dict[str, str]] = []
    for index, chart_row in data.iterrows():
        row = {key: str(value).strip() for key, value in chart_row.items()}
        fact_id = row["fact_id"]
        fact = facts.get(fact_id)
        if fact is None:
            issues.append(Issue("ERROR", "UNKNOWN_FACT_ID", f"Chart row {index + 2} references {fact_id!r}"))
            hydrated_rows.append(row)
            continue
        if fact["status"] == "unavailable":
            if row["value"]:
                issues.append(
                    Issue(
                        "ERROR",
                        "UNAVAILABLE_ENCODED_AS_VALUE",
                        f"Chart row for unavailable fact {fact_id} supplies value {row['value']!r}; keep it blank",
                    )
                )
            if row["missing_policy"] not in {"gap", "omit"}:
                issues.append(
                    Issue(
                        "ERROR",
                        "MISSING_POLICY_REQUIRED",
                        f"Unavailable fact {fact_id} requires missing_policy=gap or omit",
                    )
                )
            row["value"] = ""
        else:
            if row["value"] and row["value"] != fact["value"]:
                try:
                    same = Decimal(row["value"]) == Decimal(fact["value"])
                except InvalidOperation:
                    same = False
                if not same:
                    issues.append(
                        Issue(
                            "ERROR",
                            "FACT_VALUE_MISMATCH",
                            f"Chart value for {fact_id} is {row['value']!r}; ledger value is {fact['value']!r}",
                        )
                    )
            row["value"] = fact["value"]
        for field in ("period", "unit", "currency"):
            if row[field] and row[field] != fact[field]:
                issues.append(
                    Issue(
                        "ERROR",
                        "FACT_FIELD_MISMATCH",
                        f"Chart {field} for {fact_id} is {row[field]!r}; ledger has {fact[field]!r}",
                    )
                )
            row[field] = fact[field]
        canonical_metric = fact["metric"]
        if row["metric"] and row["metric"] != canonical_metric:
            issues.append(
                Issue(
                    "ERROR",
                    "FACT_METRIC_MISMATCH",
                    f"Chart metric for {fact_id} is {row['metric']!r}; ledger metric is {canonical_metric!r}. "
                    "Use display_label for translated or reader-friendly text.",
                )
            )
        row["metric_code"] = canonical_metric
        row["metric"] = row["display_label"] or canonical_metric
        locator = f"{fact['locator_type']}:{fact['locator']}" if fact["locator"] else ""
        row["source"] = " ".join(part for part in (fact["source_file"], locator) if part)
        if not row["source"] and fact.get("status") == "calculated":
            row["source"] = f"calculated from {fact.get('input_fact_ids', '').strip()}".strip()
        if not row["source"] and fact.get("status") == "unavailable":
            reason = fact.get("notes", "").strip() or "reason not recorded"
            row["source"] = f"unavailable in filing: {reason}"
        hydrated_rows.append(row)
    return pd.DataFrame(hydrated_rows), issues


def _normalize_and_validate(data: pd.DataFrame, strict: bool) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    normalized = data.copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str).str.strip()

    for column in ("chart_id", "title", "period", "metric", "unit", "source"):
        blank_rows = normalized.index[normalized[column] == ""].tolist()
        if blank_rows:
            issues.append(
                Issue(
                    "ERROR",
                    "BLANK_REQUIRED_FIELD",
                    f"{column} is blank on CSV row(s): {', '.join(str(i + 2) for i in blank_rows[:10])}",
                )
            )

    values = pd.to_numeric(
        normalized["value"].where(normalized["value"] != "", np.nan),
        errors="coerce",
    )
    invalid_value = (normalized["value"] != "") & values.isna()
    if invalid_value.any():
        rows = [str(i + 2) for i in normalized.index[invalid_value].tolist()]
        issues.append(Issue("ERROR", "NON_NUMERIC_VALUE", f"Non-numeric value on CSV row(s): {', '.join(rows)}"))
    non_finite = values.notna() & ~np.isfinite(values)
    if non_finite.any():
        rows = [str(i + 2) for i in normalized.index[non_finite].tolist()]
        issues.append(Issue("ERROR", "NON_FINITE_VALUE", f"NaN/Inf value on CSV row(s): {', '.join(rows)}"))
    normalized["value_num"] = values

    normalized["series_key"] = normalized["metric_code"].where(
        normalized["metric_code"] != "", normalized["metric"]
    )

    duplicate = normalized.duplicated(subset=["chart_id", "period", "series_key"], keep=False)
    if duplicate.any():
        keys = normalized.loc[
            duplicate, ["chart_id", "period", "series_key"]
        ].drop_duplicates().to_dict("records")
        issues.append(Issue("ERROR", "DUPLICATE_POINT", f"Duplicate chart points: {keys[:8]}"))

    if strict:
        if (normalized["render"] == "").any():
            issues.append(
                Issue("ERROR", "STRICT_REQUIRES_RENDER", "Strict mode requires explicit render on every row")
            )
        if (normalized["axis"] == "").any():
            issues.append(
                Issue("ERROR", "STRICT_REQUIRES_AXIS", "Strict mode requires explicit axis on every row")
            )
        if (normalized["kind"] != "").any():
            issues.append(
                Issue("ERROR", "STRICT_REJECTS_LEGACY_KIND", "Strict mode rejects legacy kind; use render and axis")
            )

    rendered: list[str] = []
    inferred_combo = False
    ambiguous_bar_line = False
    unsupported_values: set[str] = set()
    for _, row in normalized.iterrows():
        explicit = row.get("render", "")
        kind = row.get("kind", "")
        if explicit:
            render = explicit
        elif kind in {"bar", "grouped_bar"}:
            render = "bar"
        elif kind == "line":
            render = "line"
        elif kind == "stacked_bar":
            render = "stacked_bar"
        elif kind == "combo_bar_line":
            render = "line" if _is_ratio(row["metric"], row["unit"]) else "bar"
            inferred_combo = True
        elif kind == "bar_line":
            render = ""
            ambiguous_bar_line = True
        else:
            render = ""
            unsupported_values.add(explicit or kind)
        rendered.append(render)
    normalized["render_norm"] = rendered
    if ambiguous_bar_line:
        issues.append(
            Issue(
                "ERROR",
                "AMBIGUOUS_BAR_LINE",
                "kind=bar_line does not identify which series is a bar or line; add an explicit render column",
            )
        )
    for value in sorted(unsupported_values):
        issues.append(Issue("ERROR", "UNSUPPORTED_RENDER", f"Unsupported render/kind {value!r}"))
    if inferred_combo:
        issues.append(
            Issue(
                "WARN",
                "INFERRED_COMBO_RENDER",
                "combo_bar_line series types were inferred from metric/unit text; use explicit render",
            )
        )
    invalid_render = ~normalized["render_norm"].isin({"bar", "line", "stacked_bar"})
    if invalid_render.any() and not any(
        issue.code in {"UNSUPPORTED_RENDER", "AMBIGUOUS_BAR_LINE"} for issue in issues
    ):
        issues.append(Issue("ERROR", "UNSUPPORTED_RENDER", "render must be bar, line, or stacked_bar"))

    normalized["axis_norm"] = normalized["axis"]
    for chart_id, indexes in normalized.groupby("chart_id", sort=False).groups.items():
        chart_rows = normalized.loc[indexes]
        has_bar = chart_rows["render_norm"].isin({"bar", "stacked_bar"}).any()
        for index in indexes:
            if normalized.at[index, "axis_norm"]:
                continue
            render = normalized.at[index, "render_norm"]
            metric = normalized.at[index, "metric"]
            unit = normalized.at[index, "unit"]
            normalized.at[index, "axis_norm"] = (
                "secondary" if has_bar and render == "line" and _is_ratio(metric, unit) else "primary"
            )
    invalid_axis = ~normalized["axis_norm"].isin({"primary", "secondary"})
    if invalid_axis.any():
        issues.append(Issue("ERROR", "INVALID_AXIS", "axis must be primary or secondary"))
    if ((normalized["render_norm"] != "line") & (normalized["axis_norm"] == "secondary")).any():
        issues.append(Issue("ERROR", "SECONDARY_BAR_UNSUPPORTED", "Only line series may use the secondary axis"))

    for chart_id, group in normalized.groupby("chart_id", sort=False):
        titles = set(group["title"])
        if len(titles) != 1:
            issues.append(Issue("ERROR", "TITLE_CONFLICT", f"{chart_id}: multiple titles {sorted(titles)}"))
        if "stacked_bar" in set(group["render_norm"]) and set(group["render_norm"]) != {"stacked_bar"}:
            issues.append(
                Issue("ERROR", "STACKED_MIXED_RENDER", f"{chart_id}: stacked_bar cannot mix with other renders")
            )
        label_codes = group.groupby("metric", sort=False)["metric_code"].agg(
            lambda values: {value for value in values if value}
        )
        for label, codes in label_codes.items():
            if len(codes) > 1:
                issues.append(
                    Issue(
                        "ERROR",
                        "DISPLAY_LABEL_COLLISION",
                        f"{chart_id}: display label {label!r} maps to multiple canonical metrics {sorted(codes)}",
                    )
                )
        for metric, series in group.groupby("series_key", sort=False):
            if len(set(series["render_norm"])) > 1:
                issues.append(Issue("ERROR", "SERIES_RENDER_CONFLICT", f"{chart_id}/{metric}: render changes by period"))
            if len(set(series["axis_norm"])) > 1:
                issues.append(Issue("ERROR", "SERIES_AXIS_CONFLICT", f"{chart_id}/{metric}: axis changes by period"))
            if len(set(series["unit"])) > 1:
                issues.append(Issue("ERROR", "SERIES_UNIT_CONFLICT", f"{chart_id}/{metric}: unit changes by period"))
        try:
            periods = _period_order(group)
        except (ValueError, TypeError) as exc:
            issues.append(Issue("ERROR", "INVALID_PERIOD_ORDER", f"{chart_id}: {exc}"))
            periods = list(dict.fromkeys(group["period"].tolist()))
        series_keys = list(dict.fromkeys(group["series_key"].tolist()))
        present = set(zip(group["series_key"], group["period"]))
        missing_points = [
            (series_key, period)
            for series_key in series_keys
            for period in periods
            if (series_key, period) not in present
        ]
        if missing_points:
            severity = "ERROR" if "stacked_bar" in set(group["render_norm"]) else "WARN"
            code = "STACKED_SERIES_INCOMPLETE" if severity == "ERROR" else "INCOMPLETE_SERIES_MATRIX"
            issues.append(
                Issue(
                    severity,
                    code,
                    f"{chart_id}: missing explicit series-period rows {missing_points[:12]}; "
                    "add unavailable facts with gap/omit policy instead of leaving cells implicit",
                )
            )
        for axis, axis_group in group.groupby("axis_norm", sort=False):
            units = set(axis_group["unit"])
            if len(units) > 1:
                issues.append(
                    Issue("ERROR", "MIXED_AXIS_UNITS", f"{chart_id}/{axis}: mixed units {sorted(units)}")
                )
            currencies = {item for item in axis_group["currency"] if item and item != "N/A"}
            if len(currencies) > 1:
                issues.append(
                    Issue("ERROR", "MIXED_AXIS_CURRENCIES", f"{chart_id}/{axis}: mixed currencies {sorted(currencies)}")
                )
        if (group["axis_norm"] == "secondary").all():
            issues.append(Issue("ERROR", "SECONDARY_WITHOUT_PRIMARY", f"{chart_id}: all series use secondary axis"))
        if (group["axis_norm"] == "secondary").any() and not (group["axis"] != "").all():
            issues.append(
                Issue("WARN", "INFERRED_AXIS", f"{chart_id}: at least one axis was inferred; specify axis explicitly")
            )
        missing = group["value_num"].isna()
        if missing.any():
            policies = set(group.loc[missing, "missing_policy"])
            if not policies <= {"gap", "omit"} or "" in policies:
                issues.append(
                    Issue("ERROR", "MISSING_VALUE_POLICY", f"{chart_id}: missing values require gap or omit policy")
                )
            if "stacked_bar" in set(group["render_norm"]):
                issues.append(
                    Issue("ERROR", "STACKED_MISSING_VALUE", f"{chart_id}: stacked charts cannot imply missing values are zero")
                )

    slugs: defaultdict[str, list[str]] = defaultdict(list)
    for chart_id in normalized["chart_id"].drop_duplicates():
        slugs[_slug(chart_id)].append(chart_id)
    for slug, chart_ids in slugs.items():
        if len(chart_ids) > 1:
            issues.append(Issue("ERROR", "SLUG_COLLISION", f"Chart IDs {chart_ids} map to output slug {slug!r}"))

    if strict and not normalized["fact_id"].astype(str).str.strip().all():
        issues.append(Issue("ERROR", "STRICT_REQUIRES_FACT_IDS", "Strict mode requires fact_id on every row"))
    return normalized, issues


def _period_order(group: pd.DataFrame) -> list[str]:
    first_seen = list(dict.fromkeys(group["period"].tolist()))
    explicit: dict[str, float] = {}
    for period, rows in group.groupby("period", sort=False, observed=False):
        raw = {item for item in rows["period_order"] if item}
        if len(raw) > 1:
            raise ValueError(f"period {period!r} has conflicting period_order values")
        if raw:
            value = float(next(iter(raw)))
            if not math.isfinite(value):
                raise ValueError(f"period {period!r} has a non-finite period_order")
            explicit[period] = value
    if explicit and len(explicit) != len(first_seen):
        raise ValueError("period_order must be provided for every period or none")
    return sorted(first_seen, key=explicit.get) if explicit else first_seen


def _axis_label(group: pd.DataFrame, axis: str) -> str:
    units = [value for value in group.loc[group["axis_norm"] == axis, "unit"].unique() if value]
    currencies = [
        value
        for value in group.loc[group["axis_norm"] == axis, "currency"].unique()
        if value and value != "N/A"
    ]
    unit = units[0] if units else ""
    currency = currencies[0] if currencies else ""
    return f"{unit} ({currency})" if unit and currency else unit or currency


def _plot_lines(
    ax: plt.Axes,
    data: pd.DataFrame,
    periods: list[str],
    colors: Sequence[str] | None = None,
) -> None:
    x = np.arange(len(periods))
    for index, (metric, series) in enumerate(data.groupby("metric", sort=False)):
        mapping = dict(zip(series["period"], series["value_num"]))
        y = [mapping.get(period, np.nan) for period in periods]
        color = colors[index % len(colors)] if colors else None
        ax.plot(x, y, marker="o", linewidth=2.2, label=metric, color=color)


def _anchor_axis_at_zero(ax: plt.Axes, values: pd.Series) -> None:
    finite = pd.to_numeric(values, errors="coerce")
    finite = finite[np.isfinite(finite)]
    if finite.empty:
        return
    if (finite >= 0).all():
        ax.set_ylim(bottom=0)
    elif (finite <= 0).all():
        ax.set_ylim(top=0)


def plot_chart(group: pd.DataFrame, output_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    chart_id = group.iloc[0]["chart_id"]
    title = group.iloc[0]["title"]
    slug = _slug(chart_id)
    output = output_dir / f"{slug}.png"
    data_output = output_dir / f"{slug}.data.csv"
    input_periods = _period_order(group)
    audit_data = group.copy()
    audit_data["period"] = pd.Categorical(
        audit_data["period"], categories=input_periods, ordered=True
    )
    audit_data = audit_data.sort_values(["period", "metric"], kind="stable")
    audit_data.to_csv(
        data_output,
        index=False,
        columns=[
            "chart_id",
            "title",
            "fact_id",
            "period",
            "metric_code",
            "metric",
            "value_num",
            "unit",
            "currency",
            "render_norm",
            "axis_norm",
            "source",
            "missing_policy",
        ],
    )

    omitted = audit_data[
        audit_data["value_num"].isna() & (audit_data["missing_policy"] == "omit")
    ].copy()
    working = audit_data.drop(index=omitted.index).copy()
    if working.empty:
        raise ValueError(f"{chart_id}: every point is unavailable with missing_policy=omit")
    periods = _period_order(working)
    working["period"] = pd.Categorical(working["period"], categories=periods, ordered=True)
    working = working.sort_values(["period", "metric"], kind="stable")

    fig, ax = plt.subplots(figsize=(9, 5.2), constrained_layout=True)
    ax2: plt.Axes | None = None
    x = np.arange(len(periods))

    primary = working[working["axis_norm"] == "primary"]
    renders = set(primary["render_norm"])
    if renders == {"stacked_bar"}:
        pivot = primary.pivot(index="period", columns="metric", values="value_num").reindex(periods)
        pivot.plot(kind="bar", stacked=True, ax=ax, width=0.78)
    else:
        bars = primary[primary["render_norm"] == "bar"]
        if not bars.empty:
            pivot = bars.pivot(index="period", columns="metric", values="value_num").reindex(periods)
            pivot.plot(kind="bar", ax=ax, width=0.78)
        lines = primary[primary["render_norm"] == "line"]
        if not lines.empty:
            _plot_lines(ax, lines, periods)

    secondary = working[working["axis_norm"] == "secondary"]
    if not secondary.empty:
        ax2 = ax.twinx()
        _plot_lines(ax2, secondary, periods, colors=("#d95f02", "#7570b3", "#e7298a"))
        ax2.set_ylabel(_axis_label(working, "secondary"))
        _anchor_axis_at_zero(ax2, secondary["value_num"])

    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel(_axis_label(working, "primary"))
    _anchor_axis_at_zero(ax, primary["value_num"])
    ax.set_xticks(x)
    ax.set_xticklabels(periods, rotation=30, ha="right")
    ax.grid(axis="y", alpha=0.25)

    handles, labels = ax.get_legend_handles_labels()
    if ax2 is not None:
        handles2, labels2 = ax2.get_legend_handles_labels()
        handles += handles2
        labels += labels2
        if ax2.get_legend() is not None:
            ax2.get_legend().remove()
    if handles:
        if ax.get_legend() is not None:
            ax.get_legend().remove()
        ax.legend(handles, labels, loc="best", frameon=True)

    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)

    series_manifest: list[dict[str, Any]] = []
    for metric_code, series in working.groupby("series_key", sort=False):
        series_manifest.append(
            {
                "metric_code": metric_code,
                "display_label": series.iloc[0]["metric"],
                "render": series.iloc[0]["render_norm"],
                "axis": series.iloc[0]["axis_norm"],
                "unit": series.iloc[0]["unit"],
                "currency": series.iloc[0]["currency"],
                "fact_ids": [item for item in series["fact_id"] if item],
                "sources": list(dict.fromkeys(item for item in series["source"] if item)),
            }
        )
    manifest = {
        "chart_id": chart_id,
        "title": title,
        "output": output.name,
        "data_file": data_output.name,
        "periods": periods,
        "series": series_manifest,
        "missing_values_are_gaps_not_zero": bool(working["value_num"].isna().any()),
        "omitted_unavailable_points": [
            {
                "fact_id": row["fact_id"],
                "period": str(row["period"]),
                "metric_code": row["series_key"],
                "display_label": row["metric"],
                "source": row["source"],
            }
            for _, row in omitted.iterrows()
        ],
    }
    return output, data_output, manifest


def _print_issues(issues: Sequence[Issue]) -> None:
    for issue in issues:
        print(f"{issue.severity} [{issue.code}]: {issue.message}", file=sys.stderr)
    errors = sum(issue.severity == "ERROR" for issue in issues)
    warnings = sum(issue.severity == "WARN" for issue in issues)
    print(f"VALIDATION errors={errors} warnings={warnings}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Chart specification or legacy long-form CSV")
    parser.add_argument("--facts", type=Path, help="Validated caiwu-fenxi fact ledger")
    parser.add_argument("--out", type=Path, default=Path("charts"), help="Output directory")
    parser.add_argument("--strict", action="store_true", help="Require fact IDs and fail on warnings")
    parser.add_argument("--validate-only", action="store_true", help="Validate without creating outputs")
    args = parser.parse_args()

    frame, issues = _load_chart_csv(args.csv.expanduser().resolve())
    if frame is None:
        _print_issues(issues)
        return 1
    facts: dict[str, dict[str, str]] | None = None
    if args.facts:
        facts, fact_issues = _load_facts(args.facts.expanduser().resolve())
        issues.extend(fact_issues)
    data, hydrate_issues = _hydrate_from_facts(frame, facts, args.strict)
    issues.extend(hydrate_issues)
    data, validation_issues = _normalize_and_validate(data, args.strict)
    issues.extend(validation_issues)
    _configure_font(" ".join(data["title"].tolist() + data["metric"].tolist()), issues)

    _print_issues(issues)
    has_errors = any(issue.severity == "ERROR" for issue in issues)
    has_warnings = any(issue.severity == "WARN" for issue in issues)
    if has_errors or (args.strict and has_warnings):
        return 1
    if args.validate_only:
        return 0

    output_dir = args.out.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests: list[dict[str, Any]] = []
    outputs: list[Path] = []
    try:
        for _, group in data.groupby("chart_id", sort=False):
            output, data_output, manifest = plot_chart(group, output_dir)
            outputs.extend((output, data_output))
            manifests.append(manifest)
    except (ValueError, KeyError) as exc:
        print(f"ERROR [RENDER_FAILED]: {exc}", file=sys.stderr)
        return 1

    manifest_path = output_dir / "chart_manifest.json"
    manifest_path.write_text(json.dumps(manifests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    captions_path = output_dir / "captions.md"
    caption_lines = ["# Chart Captions", ""]
    for item in manifests:
        units = sorted({series["unit"] for series in item["series"] if series["unit"]})
        currencies = sorted(
            {
                series["currency"]
                for series in item["series"]
                if series["currency"] and series["currency"] != "N/A"
            }
        )
        sources = list(
            dict.fromkeys(source for series in item["series"] for source in series["sources"])
        )
        facts_used = [fact for series in item["series"] for fact in series["fact_ids"]]
        caption_lines.append(
            f"- **{item['title']}** (`{item['output']}`): periods {', '.join(item['periods'])}; "
            f"units {', '.join(units) or 'N/A'}; currencies {', '.join(currencies) or 'N/A'}."
        )
        caption_lines.append(f"  Sources: {'; '.join(sources) or 'legacy CSV; no fact ledger link'}.")
        if facts_used:
            caption_lines.append(f"  Fact IDs: {', '.join(facts_used)}.")
        if item["missing_values_are_gaps_not_zero"]:
            caption_lines.append("  Missing values are shown as gaps, not zeros.")
        if item["omitted_unavailable_points"]:
            omitted_text = "; ".join(
                f"{point['display_label']}@{point['period']} ({point['fact_id']})"
                for point in item["omitted_unavailable_points"]
            )
            caption_lines.append(f"  Explicitly omitted unavailable points: {omitted_text}.")
    captions_path.write_text("\n".join(caption_lines) + "\n", encoding="utf-8")
    outputs.extend((manifest_path, captions_path))
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
