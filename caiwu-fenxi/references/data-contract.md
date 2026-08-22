# Evidence and Calculation Contract

Use this contract for a substantial analysis: more than one filing, any derived
quarter, a peer comparison, a chart pack, or a report that will feed a score or
ranking. A narrow answer about one disclosed fact may use a smaller evidence
table, but the same period, scope, and locator rules still apply.

## Contents

1. Build the fact ledger before drafting
2. Use stable source locators
3. Preserve period semantics
4. Preserve statement scope and metric identity
5. Handle acquisitions and diversified businesses
6. Apply calculation conventions
7. Control peer comparisons
8. Validate before delivery

## 1. Build the Fact Ledger Before Drafting

Create one row per fact per period. Do not use the prose report or a chart as the
only store of extracted numbers. Use these CSV columns:

```text
fact_id,company,metric,period,period_type,scope,attribution,value,unit,currency,status,audit_status,source_file,locator_type,locator,source_line_item,formula,input_fact_ids,notes
```

Field rules:

- `fact_id`: unique, stable ID used by calculations.
- `metric`: use a specific canonical name; do not use an ambiguous label such as
  `profit`, `margin`, `capex`, or `net_cash` without the definition below.
- `period`: include the actual fiscal period, for example `FY2025`, `2025Q1`,
  `2025H1`, `2025-09-30`, or `2025-01-01/2025-09-30`.
- `period_type`: one of `instant`, `quarter`, `ytd`, `half_year`, `nine_month`,
  `fy`, `ttm`, or `other`.
- `scope`: use `consolidated`, `parent`, `segment:<reported name>`, or `other`.
- `attribution`: use `total`, `parent`, `nci`, or `na`. `parent` means attributable
  to owners of the parent; it does not mean the parent-company-only statement.
- `value`: normalized numeric value with no thousands separator. Preserve the
  reported sign. Leave blank only for `status=unavailable`.
- `unit`: use `yuan`, `thousand_yuan`, `ten_thousand_yuan`, `million`,
  `hundred_million`, `percent`, `ratio`, `days`, `shares`, `units`, or an equally
  explicit source unit.
- `currency`: use an ISO code such as `CNY`, `USD`, or `N/A` for non-currency
  measures. Do not silently translate currency.
- `status`: one of `reported`, `calculated`, or `unavailable`. Analytical
  inference belongs in a claim/evidence table, not as a numeric fact.
- `audit_status`: one of `audited`, `reviewed`, `unaudited`, `mixed`, or
  `unknown`.
- `source_file`: exact local path, relative to the ledger/source root or absolute.
  For a web source, save or export the cited source artifact and record its URL,
  title, and retrieval date in `notes`.
- `locator_type`: one of `pdf_page`, `printed_page`, `text_line`, `section`, or
  `note`.
- `locator`: use one-based PDF page numbers for `pdf_page`, printed page numbers
  only for `printed_page`, and extractor line ranges only for `text_line`.
- `source_line_item`: preserve the exact disclosed label, such as
  `归属于上市公司股东的净利润`.
- `formula` and `input_fact_ids`: required for a calculated fact. Separate input
  IDs with semicolons. Formulas may contain only declared fact IDs, numeric
  constants, parentheses, `+`, `-`, `*`, `/`, `**`, and `abs(...)`; the
  validator recomputes the result. For YoY/growth facts, list the current-period
  fact first and the prior-period denominator last. If the denominator is zero
  or negative, record the growth rate as unavailable/`N/M` and report the
  absolute change instead of a misleading percentage.
- A calculated fact may use only valid numeric inputs. If any required input is
  `unavailable`, the result must also remain unavailable; never substitute zero
  merely to make a formula or chart run.
- `notes`: record restatement, unit conversion, currency conversion, scope
  change, source conflict, or why a fact is unavailable.

For every material conclusion, keep a short claim/evidence table linking the
claim to fact IDs and classify it as `source-stated`, `calculated`, or
`inference`. Do not let an executive-summary statement introduce a number or
cause that is absent from the ledger or claim/evidence table.
Reuse one `claim_id` and one evidence classification wherever a conclusion is
repeated. A statement may not silently change from `inference` in the body to
`source-stated` in the summary.

In Markdown, use `[F:fact_id]` after a material reported or calculated number.
Evidence markers inside HTML comments or fenced examples do not support visible
report claims.
Use `[C:claim_id|source-stated]`, `[C:claim_id|calculated]`, or
`[C:claim_id|inference]` after a material conclusion. These compact markers let
the report linter verify references without repeating a long filename on every
sentence; keep the complete filename and locator in the ledger.

## 2. Use Stable Source Locators

- Cite the exact source file plus a typed locator. `annual report p.10` is not an
  exact filename unless a source manifest maps an ID such as `S1` to the file.
- Never label an extractor line number or a section title as `p.`. Use
  `text_line` or `section` explicitly.
- For a PDF, distinguish one-based PDF page from the printed page shown in the
  document. State which convention the report uses.
- Check that a cited PDF page is within the file's page count and a cited text
  line is within the extracted file's line count.
- If OCR was used, mark the row `OCR; rechecked` or `OCR; not rechecked` in
  `notes`. Do not treat unverified OCR as source-exact.
- When two filings disagree, keep both rows, mark the superseded or restated
  status in `notes`, and identify the comparison row selected.

## 3. Preserve Period Semantics

Create a period matrix before comparisons. Include the fiscal start/end dates,
whether the figure is point-in-time or flow, and whether a flow is single-period
or cumulative.

For Chinese A-share filings, apply these defaults unless the filing explicitly
states otherwise:

- Balance-sheet figures are point-in-time at the report date.
- Q1 income-statement and cash-flow figures cover Q1 and are also year-to-date.
- H1 income-statement and cash-flow figures are cumulative for six months.
- Q3 report income-statement and cash-flow figures are normally cumulative for
  nine months, even when the balance sheet is at September 30.
- A single Q2 may be calculated as H1 minus Q1; a single Q3 as 9M minus H1; and a
  single Q4 as FY minus 9M only when accounting policy, consolidation scope,
  currency, unit, and restatement basis match. Record both input fact IDs and the
  subtraction formula.
- If the annual filing directly discloses a quarterly table, label the figure
  `reported quarter`; do not describe it as a derived quarter.

Never annualize a quarter, run-rate it, or infer a full year unless the user asks
for that scenario. If requested, keep it outside the reported-fact table and
label the method and limitation prominently.

## 4. Preserve Statement Scope and Metric Identity

Keep these identities separate:

- `revenue`, `cost_of_revenue`, and `gross_profit` use the same statement scope.
- `gross_margin_total` is based on consolidated total revenue and total cost.
- `gross_margin_main_business` is the filing's main-business subtotal.
- `gross_margin_segment:<name>` uses the disclosed segment or product scope.
  Never substitute one for another because the values are close.
- `net_profit_total`, `net_profit_parent`, `net_profit_nci`, and
  `net_profit_parent_ex_nonrecurring` are different metrics. Reconcile total to
  parent plus NCI when all three are available.
- Distinguish parent-company-only statements from consolidated statements. The
  word `母公司` in a note or equity-incentive table does not make it a
  consolidated amount.
- Distinguish R&D expense, total R&D investment, capitalized R&D, and additions
  to development costs.
- Distinguish closing balance, average balance, cash movement, and P&L charge.

## 5. Handle Acquisitions and Diversified Businesses

- Record the acquisition date, consolidation start date, ownership percentage,
  exact post-acquisition contribution disclosed in the consolidated filing, and
  any eliminations or purchase-price effects.
- Do not subtract a target's standalone full-quarter or full-year revenue from a
  parent's consolidated partial-period revenue to call the residual `organic`.
  Use an organic or like-for-like measure only when the company discloses it or
  when exact same-period contribution and eliminations are available.
- For diversified companies, add a business-mix table. Tag every conclusion as
  consolidated or segment-specific. Do not apply a pure-play semiconductor KPI
  or causal conclusion to the whole company when the relevant business is only
  one part of consolidated revenue and segment assets/cash flow are unavailable.

## 6. Apply Calculation Conventions

- `free_cash_flow_ppe = operating_cash_flow - cash_paid_for_ppe`.
- `free_cash_flow_long_term_assets = operating_cash_flow -
  cash_paid_for_ppe_intangibles_and_other_long_term_assets`.
- For Chinese filings, the cash-flow line `购建固定资产、无形资产和其他长期资产支付的现金`
  supports the second definition, not a pure PPE definition. State which FCF is
  used and do not compare the two variants as if identical.
- `net_cash = cash_and_cash_equivalents - interest_bearing_debt`. Do not add all
  trading financial assets by default.
- If verified short-term deposits or wealth-management products are included,
  call the measure `net_liquidity`, list every component, and explain maturity,
  redemption, restriction, and valuation risk.
- Name the cash-conversion denominator: `OCF / net_profit_parent` or
  `OCF / net_profit_total`. Do not switch denominators across periods or peers.
- Use average balance for DSO, inventory days, asset turnover, and similar
  turnover metrics when both opening and closing balances are available. State
  the day count and included balance-sheet items.
- For negative or near-zero denominators, use `N/M` rather than a dramatic
  percentage. Keep absolute change visible.
- Keep overlapping government-support views separate. `Other income`,
  `non-operating income`, cost offsets, deferred-grant balances, cash receipts,
  and the non-recurring-item table may describe the same grant from different
  statement views. Reconcile them; do not add them unless the filing proves the
  amounts are mutually exclusive.
- Preserve exact non-recurring line-item names. A combined line such as
  `fair-value changes and disposal gains` is not the same as the income-statement
  `fair-value change gain`; also distinguish pre-tax, after-tax, and
  parent-attributable amounts.
- Before writing `price increase`, `ASP decline`, or `price-for-volume`, calculate
  a same-product, same-unit, same-period, same-scope revenue-per-unit bridge. If
  mix, acquisition, FX, or unit definitions are not aligned, call the result
  `implied reported revenue per unit`, not price or ASP.
- After discussing negative FCF or a funding gap, reconcile operating, investing,
  financing, FX, and opening-to-closing cash. Include debt, equity/NCI injections,
  asset sales, and cash drawdown; do not name one funding source from a balance
  change alone.

## 7. Control Peer Comparisons

- Source every peer value from that peer's filing or a validated peer ledger.
  Do not copy a peer number from another narrative report.
- Match company, metric definition, period, period type, scope, attribution,
  unit, currency, audit status, and restatement basis before placing values in
  one row.
- Put a source ID or fact ID in each peer-table cell or row. If definitions are
  not compatible, show `N/C` (not comparable) and explain why.
- Reconcile any value that differs from a peer's own report before publishing.
- In a distribution model, distinguish billed distributor/customer concentration
  from end-customer or end-demand concentration. Do not infer one from the other.

For acquisitions, search the business-combination note for the acquired entity's
revenue, profit, and cash flow from purchase date to period end before writing
`not disclosed`. For new products, search both the business discussion and the
segment/revenue notes; a validation or mass-production label alone neither proves
nor disproves current-period revenue contribution.

## 8. Validate Before Delivery

Run the bundled validator on the fact ledger, then on the draft report:

```bash
python scripts/validate_analysis.py facts facts.csv --source-root /path/to/sources
python scripts/validate_analysis.py report report.md --facts facts.csv --semiconductor --strict
```

Resolve every error. Review every warning; either fix it or document why it is
acceptable. Validation is a guardrail, not a substitute for reading the filing.

A validated semiconductor FY ledger is an input to `jibenmian-pingfen`, not a
score. Map it with `jibenmian-pingfen/scripts/prepare_score_input.py`. Do not
hand-copy raw line items into `score-input.csv`, and do not send this ledger to
`jibenmian-pingfen-local-data` or `compare-semiconductor-fundamentals`.
