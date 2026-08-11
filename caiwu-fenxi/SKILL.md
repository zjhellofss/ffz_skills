---
name: caiwu-fenxi
description: >-
  Analyze company financial reports, annual reports, quarterly reports, earnings
  releases, footnotes, MD&A, audit notes, and related industry reports to
  produce detailed plain-language reports for non-specialists. Use when Codex
  needs to compare multiple periods or multiple filings, explain key financial
  statement changes, interpret important notes and accounting policies, analyze
  stock fundamentals, expectation points, and risk points with objective
  source-backed reasoning, build validated fact ledgers, add grounded annotations,
  or create reproducible Python-generated financial charts while strictly
  preserving source-reported data and avoiding unsupported claims. For
  semiconductor companies, including chip design/fabless,
  IDM, foundry, OSAT, equipment, materials, and EDA/IP, apply subsector-specific
  operating metrics, commercialization stages, cycle, inventory, capacity, order,
  acceptance, capex, depreciation, subsidy, and supply-chain checks.
---

# Analyze Financial Reports

## Core Rule

Ground every material number, comparison, and conclusion in the provided filings or explicitly cited external sources. Do not estimate, interpolate, annualize, normalize, or infer missing data unless the user asks for that calculation and the method is clearly labeled.

For any substantial report (multiple filings, derived quarters, peer data, charts, or an output that feeds scoring), use `references/data-contract.md`: build the fact ledger before prose, cite material numbers with `[F:fact_id]`, and keep material conclusions in a claim/evidence table. The ledger is the single source for prose, comparisons, and charts. Never encode a financial value directly in chart code or turn an unavailable value into zero.

Output language: write the report in the user's language. If the user's language is unclear, default to the language of the filings; for Chinese-language filings default to Chinese. When quoting an original line-item name, figure, or label, keep the source text verbatim and add a short gloss in the report language. Use the report language for chart titles, labels, captions, and notes.

## Workflow

1. Inventory sources before analysis.
   - Identify company, filing type, reporting period, currency, accounting standard, consolidation scope, publication date, and fiscal year-end date.
   - Separate primary sources (annual reports, 10-K/20-F, 10-Q, audited financial statements, earnings releases) from secondary sources (industry reports, analyst reports, news).
   - If current facts, market data, regulations, or industry context may have changed, verify with current sources and cite them.

2. Extract and validate facts before drafting.
   - Follow `references/data-contract.md`. Record period type, statement scope, profit attribution, original line item, value, unit, currency, audit status, exact source file, typed locator, and restatement status.
   - Distinguish one-based PDF pages, printed pages, extracted-text lines, sections, and notes. Never label a text line or section as `p.`. Check that the source file and cited range exist.
   - Preserve signs, units, currencies, and restatement labels exactly. Convert units only as an explicit calculated fact linked to the original fact ID.
   - Exhaust the filing's comparison columns and notes before deriving a missing value. A value reconstructed from a rounded growth rate is calculated, not reported, and must show its uncertainty.
   - Run `python scripts/validate_analysis.py facts facts.csv --source-root /path/to/sources`. Resolve errors before drafting; review and document warnings.

3. Extract business background, core products, and technology roadmap.
   - Read the filing sections describing company profile, principal activities, business model, product/service portfolio, segment/application markets, R&D projects, technology roadmap, commercialization stage, capacity expansion, customer validation, and major operating risks.
   - Explain how the company's products or services map to reported revenue segments, major growth drivers, margin changes, and capital expenditure plans.
   - For technology-heavy or manufacturing companies, distinguish products already in mass production, products in customer validation or small-batch delivery, and products still in R&D when the filings disclose those stages.
   - When filings use domain-specific product names, acronyms, technical standards, model numbers, or technology routes, add plain-language explanations and state why each matters financially.
   - Do not add technical claims from memory. If product details, technology route, or commercialization stage are not disclosed, mark them unavailable or cite an external authoritative source when current context is necessary.
   - For semiconductor companies, first classify each material business as chip design/fabless, IDM, foundry, OSAT, semiconductor equipment, semiconductor materials, or EDA/IP. A diversified company may require more than one classification. Then apply `references/semiconductor-framework.md`, use the applicable metrics in `references/semiconductor-metrics.md`, and run the additional checks in `references/semiconductor-red-flags.md`.
   - Do not use one semiconductor subsector's KPI set as a generic industry benchmark. In particular, do not compare fabless and manufacturing capex intensity, equipment shipments and recognized revenue, or customer validation and mass-production revenue as if they were equivalent.

4. Reconcile and validate.
   - Check whether key totals tie: assets = liabilities + equity, gross profit = revenue - cost of revenue, operating profit to net profit bridge where disclosed, and cash flow subtotals.
   - Prefer source-defined non-GAAP metrics over self-created metrics. If calculating ratios, state formula and inputs.
   - Flag missing periods, changed segments, accounting policy changes, restatements, acquisitions, disposals, FX effects, or one-off items before comparing trends.
   - Keep consolidated/parent/segment scope and total/parent-attributable/NCI profit identity explicit. Do not mix total gross margin with main-business or segment gross margin.
   - For an acquisition, use only the exact post-acquisition contribution for the consolidated period. Do not subtract a target's standalone full-quarter result from a parent that consolidated it for only part of the quarter and call the residual organic.

5. Compare across reports.
   - Before comparing, confirm the periods are comparable. Companies with a non-calendar fiscal year-end must not be aligned to calendar quarters; use the company-disclosed comparable period and footnote the start/end dates of both sides.
   - Compare at least the latest period versus the prior comparable period when data exists.
   - For multiple filings, explain both numeric change and likely driver, but label drivers as source-stated unless they are an analytical inference.
   - Use absolute change and percentage change together when meaningful.
   - When a report presents broad revenue or segment categories, break them down into disclosed product subcategories, application scenarios, model families, or technology routes when the filings provide enough detail. Explain each subcategory's role in the customer's system, disclosed commercialization status, and financial meaning.
   - Source peer values from each peer's filing or the same validated fact ledger. Match metric variant, period, scope, attribution, unit, currency, and restatement basis; otherwise mark `N/C`.

6. Explain notes and industry context.
   - Read material footnotes connected to major changes: revenue recognition, impairment, leases, debt, fair value, inventory, receivables, tax, contingencies, related parties, subsequent events, and segment reporting.
   - Use industry reports only to contextualize company performance; never replace company-reported figures with industry estimates.
   - Translate technical accounting into plain language without losing the accounting consequence.
   - For semiconductor companies, distinguish cyclical recovery, structural share gain, price change, volume change, product-mix change, acquisition effects, and capacity additions whenever the sources permit. If they cannot be separated, state that limitation rather than assigning a single cause.
   - Reconcile government support across other income, non-operating income, cost offsets, deferred-income balances, cash receipts, and non-recurring classifications. These may be overlapping views of the same grant and must not be added by default.
   - Use `price`, `ASP`, or `price-for-volume` only after a same-product, same-unit, same-period, same-scope bridge. Otherwise say `implied reported revenue per unit` and list mix/acquisition/FX limitations.
   - After negative FCF, complete an operating + investing + financing + FX = cash-change bridge before naming the funding source. Include debt, equity/NCI injections, and cash drawdown.

7. Analyze stock fundamentals, expectation points, and risk points objectively.
   - Include a dedicated report section for listed companies covering fundamentals, expectation points, and risk points unless the user explicitly requests a narrower output.
   - Fundamentals should synthesize source-backed evidence on business model, industry position, revenue growth, profitability, cash-flow quality, balance-sheet strength, customer/product concentration, R&D or capex needs, and governance or disclosure issues when available.
   - Expectation points should be objective, evidence-based factors that could support future performance, such as disclosed backlog/orders, capacity expansion, new product commercialization, industry demand, policy support, margin recovery, operating leverage, or balance-sheet optionality. Label each item as source-stated, calculated, or analytical inference.
   - Risk points should be equally specific and source-backed, including demand cyclicality, margin pressure, inventory or receivable risk, customer concentration, technology validation uncertainty, competition, regulation, leverage, refinancing, impairment, litigation, related-party issues, or repeated one-off gains when relevant.
   - If current market valuation, share price, consensus forecast, ownership, index inclusion, or regulatory status is discussed, verify it with current authoritative sources and cite the date. Do not use stale market data from memory.
   - Keep the tone balanced. Do not write promotional language, price targets, buy/sell/hold recommendations, or certainty claims unless the user explicitly asks for investment advice and the limits are stated.

8. Write for non-specialists.
   - Lead with what changed, why it matters, and how confident the source support is.
   - Keep jargon minimal. When jargon is necessary, define it once in a note.
   - Separate facts, calculations, and interpretation.

9. Visualize financial patterns with Python-generated charts when useful.
   - Do not use Mermaid for financial charts. Use a dedicated Python visualization library such as `matplotlib`, `seaborn`, or `plotly`; prefer static PNG/SVG outputs for reports unless the user requests interactive HTML.
   - Use `scripts/financial_charts.py` with a chart specification linked by `fact_id` to the validated fact ledger. Keep the ledger's canonical `metric` identity and put translated or reader-friendly chart text in `display_label`. Specify each series' `render` and `axis`; do not rely on metric-name guessing. Run with `--facts facts.csv --strict`.
   - The renderer rejects duplicate or incomplete series-period matrices, mixed units/currencies on one axis, canonical-metric mismatches, ambiguous bar/line definitions, unavailable-as-zero, and value mismatches; it writes normalized chart data, a manifest, and captions.
   - Default to 4–6 high-information charts selected for the company's actual issues. Consider revenue/profit, margins, cash quality, balance sheet/working capital, segment mix, and one company-specific driver; add more only when they provide distinct decision-relevant information or the user asks.
   - Add a short caption listing metric, period, unit, source, and whether values are source-reported or calculated.
   - Do not chart partial data as a complete trend. If a chart omits unavailable periods, make the omission visible in the caption or note.
   - Use professional financial-chart conventions: clear units, readable labels, non-misleading axes, comparable scales, and restrained styling. Avoid decorative charts that reduce traceability.

## Required Output Structure

Use `references/report-framework.md` for the full report template, metric list, annotation style, and Python chart guidance. Use `references/validation-checklist.md` before finalizing to catch unsupported numbers or overconfident claims.

For a substantial report, also use `references/data-contract.md`, include the fact-ledger and validation summary in the output package/appendix, and run:

```bash
python scripts/validate_analysis.py report report.md --facts facts.csv --strict
```

Add `--semiconductor` for semiconductor companies. Resolve errors; either fix each warning or explain it in the report limitations.
Use `assets/example-facts.csv`, `assets/example-chart-spec.csv`, and `assets/example-report.md` as validated schema/marker templates; replace the example values and source path rather than treating them as evidence.

For semiconductor companies, also use all three industry references:

- `references/semiconductor-framework.md` for subsector routing and the required analysis chain.
- `references/semiconductor-metrics.md` for definitions and subsector-specific operating KPIs.
- `references/semiconductor-red-flags.md` for industry-specific validation, earnings-quality signals, and open questions.

## Source Handling

- If the user provides files, inspect them directly and cite local filenames plus pages, sections, tables, or note numbers where possible.
- If the user provides links or asks for latest/current information, browse or otherwise verify against authoritative sources.
- If a figure cannot be traced, omit it or mark it unavailable; never fill gaps from memory.
- If filings disagree, prioritize audited annual filings over unaudited releases unless the annual filing is older or superseded, and explain the conflict.
- Filings are usually PDF or HTML. For PDF text and tables, prefer a programmatic extractor (e.g. `pdfplumber` or `pymupdf`); for complex multi-page or merged-cell tables, a table-specific tool (e.g. `camelot`) helps; scanned/image PDFs need OCR first, and any OCR-derived numbers must be labeled as requiring re-check. Parse HTML filings (e.g. SEC EDGAR) directly. If a table cannot be extracted reliably, mark it `[extraction failed: figure not captured]` and do not reconstruct numbers from surrounding context.
- If separate supplements are necessary, give them company-specific names and link them bidirectionally from the canonical report or a package manifest. Do not leave unlinked generic `补充报告.md` files that downstream analysis may miss.

## Final Quality Bar

The final report must let a reader trace important claims through fact IDs to exact source locations, understand the company's financial movement in ordinary language, distinguish company-reported facts from calculations and inference, and reproduce every chart and material calculation. A prose claim that "all figures are traceable" does not replace successful validation.
