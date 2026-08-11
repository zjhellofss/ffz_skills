# Financial Report Analysis Framework

## Report Template

Use this structure unless the user requests another format:

1. Executive summary
   - 3-6 bullets on the most important financial changes.
   - Include period, currency, accounting basis, and source set.
   - State any major limitations, such as missing cash flow statement or incomplete notes.
   - Link every material number to `[F:fact_id]` and every material conclusion to one consistent `[C:claim_id|classification]`.

2. Company and source scope
   - Company name, business model, reporting periods compared, filing types, and source hierarchy.
   - Table: source ID, exact filename/URL, period start/end, publication date, audited/reviewed/unaudited, currency, consolidation scope, and pages/sections used.
   - State whether page citations mean one-based PDF pages or printed pages; label extracted-text lines separately.

3. Business background, core products, and technology roadmap
   - Explain what the company does, where it sits in its industry value chain, and how it makes money.
   - Identify core products/services, application markets, customer groups, sales model, and production or delivery model using the company's own segment and product names.
   - For technology, manufacturing, biotech, software, energy, telecom, semiconductor, and other product-cycle-driven companies, summarize the disclosed technology route, product roadmap, R&D projects, commercialization stage, capacity expansion, and customer validation status.
   - Add a plain-language product and technology glossary when the report contains industry-specific product names, acronyms, model names, technical standards, molecule names, chip/process names, or regulatory shorthand that non-specialists may not know.
   - Glossary table columns: term, plain-language explanation, financial relevance, source/notes.
   - Financial relevance should connect the term to revenue mix, margin, pricing power, customer adoption, capex, inventory, R&D, regulation, or risk when the filings support that link.
   - Link product/technology changes to financial changes: revenue mix, gross margin, operating expenses, capital expenditure, inventory, receivables, and customer concentration.
   - Mark unavailable details as unavailable. Do not infer product performance, technical superiority, production yield, or customer adoption unless the filing or cited source says so.
   - For a semiconductor company, classify the material businesses and add the required subsections from `semiconductor-framework.md`. Use only the relevant subsector KPIs from `semiconductor-metrics.md`; do not force a single KPI template across design, manufacturing, equipment, materials, and EDA/IP.
   - Start semiconductor work with a seven-row coverage matrix from `semiconductor-framework.md`, marking each module `covered`, `not disclosed`, or `not material`. This preserves completeness without duplicating empty chapters.

4. Plain-language financial snapshot
   - Revenue, gross profit or margin if disclosed/calculable, operating profit, net profit, operating cash flow, capex, free cash flow if calculated, cash, debt, equity, and major segment metrics.
   - Explain each metric in ordinary language the first time it appears.
   - Generate values from the validated fact ledger. Do not retype an independent copy of the same data for the report.

5. Cross-period comparison
   - Table columns: metric, latest period, prior comparable period, absolute change, percentage change, source, comment.
   - Use `N/M` when percentage change is not meaningful, such as movement from negative to positive or near-zero base.
   - Mention restatement, FX, acquisition, disposal, segment reclassification, fiscal calendar change, or accounting policy change before interpreting growth.

6. Profitability analysis
   - Revenue drivers, cost movement, gross margin, operating expenses, operating margin, net margin, and one-off items.
   - Separate source-stated drivers from analyst inference.
   - If revenue is reported by broad product or segment categories, add a follow-on table breaking those categories into disclosed product subcategories, application scenarios, model families, or technology routes.
   - Suggested columns for the subcategory table: reported category, product subcategory/technology route, role in the customer's system or use case, disclosed status in the period, financial meaning.
   - Use this table to identify which subcategory actually explains revenue growth, margin improvement, customer concentration, inventory build, capex, or future risk. Do not present R&D-stage or customer-validation-stage products as current revenue drivers unless the filing says they contributed revenue.

7. Cash flow and balance sheet quality
   - Compare profit with operating cash flow.
   - Highlight working capital movements in receivables, inventory, payables, contract assets/liabilities, and customer advances.
   - Explain liquidity, maturity profile, leverage, covenants, and refinancing risk when debt notes are available.
   - Name the cash-conversion denominator explicitly. If NCI is material, show both `OCF / total net profit` and `OCF / parent-attributable net profit` rather than a bare `OCF / net profit`.
   - For a material funding gap, reconcile operating, investing, financing, FX, and cash change; include debt, parent/NCI equity injections, asset sales, and cash drawdown.

8. Segment and geographic performance
   - Use company segment definitions.
   - Do not merge or relabel segments unless clearly mapped.
   - Explain whether growth is broad-based or concentrated.

9. Key footnotes explained
   - Pick notes that materially affect interpretation.
   - For each note: what the note says, why a non-specialist should care, and what risk or uncertainty remains.

10. Industry context
   - Summarize relevant industry growth, pricing, regulation, commodity, demand, or competitive factors from cited sources.
   - Explain how context supports or challenges the company's reported trend.
   - Do not make investment recommendations unless explicitly requested.

11. Stock fundamentals, expectation points, and risk points
   - Use this section for listed companies unless the user explicitly requests a narrower report.
   - Start with a balanced fundamentals summary covering the company's business model, industry position, revenue growth, profitability, cash-flow quality, balance-sheet strength, customer/product concentration, R&D or capex burden, and governance or disclosure issues when the sources provide enough evidence.
   - Separate the analysis into three short subsections:
     - `Fundamentals`: what the current filings show about business quality and financial resilience.
     - `Expectation points`: source-backed factors that could support future performance, such as disclosed backlog/orders, capacity expansion, new product commercialization, industry demand, policy support, margin recovery, operating leverage, or balance-sheet optionality.
     - `Risk points`: source-backed factors that could pressure future performance, such as demand cyclicality, margin pressure, inventory or receivable build-up, customer concentration, technology validation uncertainty, competition, regulation, leverage, refinancing, impairment, litigation, related-party issues, or repeated one-off gains.
   - For every expectation or risk point, state the evidence and classify the reasoning as `source-stated`, `calculated`, or `inference`.
   - Assign a stable claim ID and reuse the same classification wherever the conclusion appears.
   - Keep positive and negative points proportional to the evidence. Avoid promotional wording, exaggerated certainty, and one-sided framing.
   - If discussing share price, valuation multiples, consensus forecasts, market capitalization, ownership, index inclusion, or current regulatory status, verify with current authoritative sources and cite the data date.
   - Do not provide price targets or buy/sell/hold recommendations unless the user explicitly requests investment advice; even then, state limitations and separate investment opinion from source-backed financial analysis.

12. Python-generated visuals
   - Default to 4-6 non-duplicative charts selected for the company's material issues; add more only when they contribute distinct information.
   - Use dedicated Python plotting tools such as `matplotlib`, `seaborn`, or `plotly`; do not use Mermaid for financial visuals.
   - Build every series from fact IDs, use `display_label` only for presentation while preserving the ledger metric code, keep unavailable values as explicit gaps/omissions, and generate the chart data snapshot, manifest, and caption. Supply a complete series-by-period matrix; never let a missing stacked segment render as an implicit zero. If chart files are produced, list the file path next to each caption.

13. Risks, watch items, and open questions
   - Do not repeat the expectation/risk table from section 11. Use this section only for unresolved evidence gaps, monitoring triggers, and questions that would change the conclusion.
   - Focus on source-backed issues: declining margins, cash conversion weakness, rising leverage, customer concentration, impairments, litigation, going concern language, covenant pressure, or repeated adjustments.
   - Include an earnings quality signal checklist when the data is available. These signals are not investment advice or fraud allegations; present them as questions a reader should investigate.
     - Net profit and operating cash flow diverge for multiple periods, especially when profit rises but operating cash flow weakens.
     - Revenue grows while receivables, contract assets, unbilled revenue, or days sales outstanding grow faster, which may indicate looser credit terms, slower collection, or revenue timing pressure.
     - "One-off", "non-recurring", or adjusted items appear repeatedly across years, suggesting the adjustment may be economically recurring.
     - Gross margin or operating margin differs materially from peers or the company's own history without a clear source-stated explanation.
     - Capitalized costs increase materially, including capitalized development costs, capitalized interest, contract acquisition costs, or other costs that could otherwise have been expensed.
     - Inventory grows faster than revenue or cost of sales, write-downs change materially, or inventory turnover weakens.
     - Significant related-party transactions, bill-and-hold arrangements, channel incentives, returns, rebates, or extended payment terms are disclosed.
     - Large impairment reversals, fair-value gains, tax credits, subsidy income, or asset disposals drive profit.
   - For semiconductor companies, also run `semiconductor-red-flags.md`, covering commercialization status, order/acceptance quality, inventory obsolescence, capacity and depreciation, government support, export controls, and single-source dependencies.
   - Include open questions when the filings do not disclose enough to conclude.

14. Appendix
   - Link `facts.csv`, chart manifest/captions, validation results, metric formulas, and notes on source conflicts.
   - The validated fact ledger replaces a separately retyped appendix table. Its conceptual shape is:

     | Line item | Period | Reported value | Unit | Currency | Source (file/page/section/note) | Note |
     |---|---|---|---|---|---|---|
     | Revenue | FY2024 | 152,300 | million | CNY | annual_2024.pdf p.12 consolidated income statement | Note 4 |
     | Revenue | FY2023 | 138,900 [recast] | million | CNY | annual_2024.pdf p.84 Note 4 prior-period column | Recast for revenue-recognition change; original 138,700 in annual_2023.pdf p.10 |

## Common Metrics and Formulas

Use formulas only when inputs are disclosed:

- Gross margin = gross profit / revenue.
- Operating margin = operating profit / revenue.
- Net margin = net profit attributable to shareholders / revenue, unless another net profit definition is clearly used.
- YoY change = latest period value - prior comparable period value.
- YoY percentage change = YoY change / absolute value of prior comparable period value.
- Current ratio = current assets / current liabilities.
- Net debt = total debt - cash and cash equivalents. Include short-term investments only if the source defines them as cash-like.
- Free cash flow (PPE) = operating cash flow - cash paid for PPE.
- Free cash flow (long-term-assets cash line) = operating cash flow - cash paid for PPE, intangibles, and other long-term assets. Do not mix the two FCF variants.
- Cash conversion (parent) = operating cash flow / parent-attributable net profit. Cash conversion (total) uses total consolidated net profit; name the selected denominator and use `N/M` when it is non-positive or near zero.
- Net cash = cash and cash equivalents - interest-bearing debt. If verified short-term investments are included, call the result net liquidity and list the components.

## Annotation Style

Use concise notes such as:

- `[Source: FY2025 annual report, consolidated income statement, p. 84]`
- `[Calculated: (2025 revenue - 2024 revenue) / 2024 revenue]`
- `[Note: Company changed segment presentation in 2025; comparisons use the recast 2024 figures disclosed in Note 3.]`
- `[Inference: Margin pressure appears linked to higher raw material costs because cost of sales rose faster than revenue; filing does not quantify this driver.]`
- `[F:fy2025_revenue]`
- `[C:margin_pressure_01|inference]`

## Plain-Language Explanations for Common Footnotes

- Revenue recognition: Explain when the company counts sales as earned, whether returns, rebates, subscriptions, contracts, or delivery obligations can shift reported revenue.
- Impairment: Explain that management reduced the carrying value of assets because expected future benefits fell.
- Fair value: Explain that some assets or liabilities are marked to market or modeled, and model assumptions can change reported gains or losses.
- Leases: Explain that long-term rental commitments often appear as both assets and liabilities.
- Debt maturity: Explain when borrowings must be repaid and whether near-term maturities could pressure cash.
- Covenants: Explain that lenders may require financial thresholds; breaches can accelerate repayment or restrict operations.
- Deferred tax: Explain timing differences between accounting profit and taxable profit.
- Contingencies: Explain unresolved legal, tax, warranty, or regulatory exposures.
- Related parties: Explain transactions with owners, executives, affiliates, or entities under common influence.
- Subsequent events: Explain material events after the reporting date that may change the reader's interpretation.

## Python Chart Guidance

Use disclosed values or calculated-and-labeled values only. Keep units in chart labels and captions. Prefer the bundled `matplotlib`/`pandas` renderer for static report charts and `plotly` when the user asks for interactive output. Save outputs as PNG or SVG files with clear filenames, and preserve the normalized data and manifest behind each chart.

Choose 4-6 from this chart set when data is available and each selected chart adds distinct information:

- Revenue and profit trend: revenue, gross profit, operating profit, net profit, and YoY growth. Use grouped bars plus a line or separate panels when scales differ.
- Margin trend: gross margin, operating margin, net margin, EBITDA margin if company-defined, and any source-defined adjusted margin.
- Cash-flow quality: net profit versus operating cash flow; free cash flow if calculated; cash conversion ratio when meaningful.
- Balance-sheet structure: assets, liabilities, equity; cash, debt, net debt; current assets versus current liabilities.
- Working capital: receivables, inventory, payables, contract assets/liabilities, and turnover or days metrics when disclosed/calculable.
- Segment, product, or geography mix: revenue and gross margin by disclosed segment; show both absolute amount and share when useful.
- Expense structure: R&D, selling, G&A, finance costs, and expense ratios to revenue.
- Debt maturity and liquidity: debt due by maturity bucket, cash and available facilities, covenant or refinancing watch items when disclosed.
- Capital allocation: capex, R&D investment, dividends, buybacks, acquisitions, and capitalized development costs when material.
- Company-specific drivers: volume/price, capacity, ARPU, users, store count, shipments, utilization, commodity cost, backlog, or other operating KPIs disclosed by the company.

Start from `assets/example-chart-spec.csv`, link each row to `facts.csv`, and run
`scripts/financial_charts.py chart-spec.csv --facts facts.csv --strict`. Do not
hard-code report numbers inside a plotting script. Use the ledger `metric` as
the canonical identity and `display_label` for translated or reader-friendly
text. Include an explicit row for every series-period cell. If data is too incomplete,
use a Markdown table and explain why no chart was produced.
