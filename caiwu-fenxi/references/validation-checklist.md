# Validation Checklist

Run this checklist before finalizing any financial report analysis.

## Mandatory Automated Gates

For a substantial report, run both commands and preserve the summary in the appendix:

```bash
python scripts/validate_analysis.py facts facts.csv --source-root /path/to/sources --strict
python scripts/validate_analysis.py report report.md --facts facts.csv --strict
```

Add `--semiconductor` to the report command for a semiconductor company. Run
`scripts/financial_charts.py chart-spec.csv --facts facts.csv --strict` before
embedding charts. Do not deliver with validation errors. Fix warnings or explain
why each one is acceptable in the limitations section.

The scripts check schema, fact IDs, source existence and locator range, duplicate
or conflicting values, calculation inputs, selected accounting identities,
report evidence markers, claim-class consistency, image existence, chart value
lineage, mixed units/currencies, missing-as-zero, and ambiguous rendering. The
human checks below remain necessary for accounting meaning and causal judgment.

## Human Review

## Source Integrity

- Every material number has a source citation or is explicitly labeled as calculated.
- Calculated figures show formula or enough inputs to reproduce.
- Units, currencies, signs, and periods match the original reports.
- Restated values are labeled as restated.
- Audited and unaudited sources are not mixed without explanation.
- Non-GAAP metrics use company definitions or are clearly labeled as analyst-calculated.
- The source inventory uses exact filenames or source IDs, not ellipses or generic labels; every listed local source exists.
- PDF pages, printed pages, text lines, sections, and notes use the correct locator type. A large text-line number is not mislabeled as a PDF page.
- Direct comparison columns and notes were searched before any value was reconstructed. A value inferred from a rounded percentage is not labeled reported and includes a rounding range.
- Report prose, summary, peer tables, and charts resolve the same metric/period/scope to the same fact ID; calculated facts never consume unavailable inputs, and missing facts are never encoded as zero.

## Comparison Integrity

- Comparisons use comparable periods: quarter vs quarter, half-year vs half-year, fiscal year vs fiscal year.
- YoY, QoQ, YTD, trailing twelve months, and full-year comparisons are not mixed without an explicit label and explanation.
- Segment changes, reporting scope changes, acquisitions, disposals, FX effects, and accounting policy changes are disclosed before trend conclusions.
- If prior-period figures were restated or recast, the report states whether comparisons use originally reported values or restated/recast values.
- Consolidation scope changes are checked. Acquisition-year or disposal-year growth is not presented as purely organic unless the source provides an organic or like-for-like measure.
- Percentage changes with negative or tiny denominators are marked not meaningful or explained.
- Absolute changes accompany percentage changes for key metrics.
- Unit conversions preserve the original reported unit in notes or table footnotes. Mixed units such as thousands, ten-thousands, millions, and hundreds of millions are reconciled before comparison.
- Rounding and precision effects from unit conversion are disclosed when they could change a percentage, subtotal, or reconciliation.
- No trend is inferred from a single data point.
- Directional prose agrees with the numbers (`higher/lower`, `rise/fall`, and sequential movement), and unusually large magnitude changes are rechecked against units and decimal placement.
- Acquisition analysis uses the exact consolidation period and searches the business-combination note for purchase-date-to-period-end revenue/profit/cash flow. Standalone full-period target data is not subtracted from a partial-period consolidation to create organic growth.
- Currency translation by itself is not used to explain a margin difference; unresolved presentation/accounting-scope conflicts are labeled unreconciled.

## Earnings Quality Review

- Profit growth is compared with operating cash flow and working-capital movements where cash flow data is available.
- Revenue growth is checked against receivables, contract assets, unbilled revenue, deferred revenue, and collection indicators when disclosed.
- Broad revenue or segment categories are broken into disclosed product subcategories or technology routes when available, and the report identifies which subcategories are current revenue drivers versus future/R&D/watch-list items.
- Repeated "one-off", "non-recurring", adjusted, or non-GAAP items are flagged when they recur across periods.
- Margin changes are compared with source-stated drivers and, where cited peer data is used, peer differences are labeled as context rather than proof.
- Capitalization-sensitive costs such as development costs, interest, contract acquisition costs, and software costs are reviewed when material.
- Earnings quality signals are phrased as watch items or open questions unless the source directly supports a stronger conclusion.
- Government grants are reconciled across other income, non-operating income, cost offsets, deferred-income balance/movement, cash receipts, and non-recurring classification; overlapping views and stock/flow measures are not added.
- Fair-value change gain, disposal gain, combined non-recurring classifications, pre-tax amount, after-tax amount, and parent-attributable amount retain their exact identities.
- Cash-conversion metrics name total or parent-attributable profit. Material NCI makes both views relevant.
- A material negative FCF conclusion includes an operating/investing/financing/FX/cash-change bridge before naming funding sources.

## Footnotes and Industry Context

- The report includes a dedicated `Business background, core products, and technology roadmap` section unless the user explicitly requested a narrower output.
- Core products/services, business model, application markets, and technology roadmap claims are cited to filings or authoritative external sources.
- Industry-specific product names, acronyms, model names, standards, and technology routes are explained in plain language for non-specialists, with financial relevance stated when source-supported.
- Product commercialization stages such as mass production, customer validation, pilot delivery, or R&D are not inferred when undisclosed.
- Important financial statement notes connected to major movements are explained.
- Industry reports are cited separately from company filings.
- Industry data is used as context, not as replacement for company-reported data.
- Accounting terms are translated into plain language without changing their meaning.
- External market, policy, and forecast facts cite the original institution, title, date, and link. A source repeated by the company filing is labeled `secondary-via-filing`, not independently verified.

## Semiconductor Industry Checks

- Each material semiconductor business is classified as chip design/fabless, IDM, foundry, OSAT, equipment, materials, or EDA/IP before KPIs or peers are selected.
- The applicable analysis chains and report additions in `semiconductor-framework.md` are completed when source data exists.
- KPI definitions follow `semiconductor-metrics.md`; similarly named capacity, utilization, shipment, order, backlog, ARR, and R&D metrics are not assumed comparable.
- Tape-out, sample, validation, pilot delivery, shipment, installation, acceptance, mass production, and recognized revenue are kept distinct.
- Announced investment, cash capex, equipment prepayments, construction in progress, transfer to fixed assets, depreciation, installed capacity, qualified capacity, and effective output are kept distinct.
- Revenue growth is tested against volume, ASP, mix, FX, acquisition, capacity, and low-base effects without forcing a decomposition that the source cannot support.
- Semiconductor inventory is reviewed by disclosed stage, including wafers/raw materials, work in process, outsourced processing, finished goods, demo tools, and goods shipped/not accepted.
- Equipment orders are checked for cancellation rights, framework status, tax basis, delivery period, shipment, acceptance, and revenue-recognition trigger.
- Customer qualification is not presented as stable volume supply without supporting evidence.
- Government grants, tax incentives, subsidized financing, and capital injections are separated and their profit/cash-flow significance is explained.
- Export-control, sanctions, licensing, market, and regulatory facts are verified using current authoritative dated sources.
- The report runs the investigation prompts and final integrity check in `semiconductor-red-flags.md`.
- The seven-row semiconductor coverage matrix is complete with `covered`, `not disclosed`, or `not material`; no module is silently omitted.
- Price/ASP claims use a same-product, same-unit, same-period, same-scope bridge. Otherwise the report says `implied reported revenue per unit` and lists mix/acquisition/FX limits.
- Distributor/customer concentration is not presented as end-customer concentration, and high supplier concentration is not called single-source dependency without evidence of exclusivity or lack of alternatives.

## Stock Fundamentals, Expectations, and Risks

- For listed companies, the report includes a dedicated `Stock fundamentals, expectation points, and risk points` section unless the user explicitly requested a narrower output.
- The fundamentals summary covers business model, industry position, growth, profitability, cash-flow quality, balance-sheet strength, concentration, investment needs, and governance or disclosure issues when source data is available.
- Expectation points are specific, evidence-based, and labeled as source-stated, calculated, or inference; they are not written as guaranteed outcomes.
- Risk points are specific, evidence-based, and at least as concrete as the positive expectation points.
- Positive and negative factors are presented proportionally to the evidence, without promotional language or one-sided framing.
- Current market data such as share price, valuation multiples, market capitalization, consensus forecasts, ownership, index inclusion, or regulatory status is verified with current authoritative sources and includes a data date.
- The report does not include price targets or buy/sell/hold recommendations unless the user explicitly requested investment advice and the limitations are stated.

## Python Charts and Visuals

- Chart values exactly match cited or calculated values.
- Chart captions include metric, period, unit, and source.
- Financial charts are generated with dedicated Python tools such as `matplotlib`, `seaborn`, or `plotly`; Mermaid is not used for financial visuals.
- Important available views are not omitted without reason: revenue/profit, margins, cash-flow quality, balance-sheet structure, working capital, leverage/liquidity, segment/geography mix, expense structure, and company-specific operating drivers.
- Chart files are named clearly, saved in a report-appropriate format such as PNG or SVG, and referenced from the report when files are produced.
- The data used for each chart is traceable to the extraction table, source citation, or explicit calculation.
- Axes and labels do not exaggerate or hide important scale effects.
- Missing periods are not visually implied as continuous data.
- Every chart has a manifest and caption with fact IDs, canonical metric codes, display labels, periods, units, currency, disclosed/calculated status, and sources. The normalized chart-data snapshot matches the ledger.
- Every multi-series chart has an explicit series-by-period matrix. Missing rows are not allowed to become implicit zero-length bars; stacked charts with any missing cell are rejected.
- Strict chart specs use `display_label`, explicit `render`, and explicit `axis`; legacy `kind` inference is not accepted.

## Language Discipline

- Claims distinguish `source-stated`, `calculated`, and `inferred`.
- The report avoids investment advice unless requested.
- The report avoids unsupported causal language such as "because" when the source only supports correlation.
- Unavailable data is marked unavailable rather than guessed.
- Material uncertainty is stated plainly.
- A repeated conclusion keeps one claim ID and one classification throughout the report; inference is not upgraded to source-stated in a later section.
- HTML comments and fenced examples cannot satisfy evidence or source gates for visible prose.
- Avoid assurance-like claims such as `no manipulation`, `profit is authentic`, `risk is controlled`, or `certainty is high` unless an authoritative source directly establishes the narrow statement. A clean audit opinion does not prove the absence of earnings-quality risk.
- If a supplement exists, it has a company-specific filename and a backlink/manifest entry from the canonical report so downstream work cannot silently omit it.
