# Semiconductor Metrics Dictionary

Use only metrics supported by company filings or authoritative cited sources. Preserve source definitions; similarly named metrics may not be comparable. Mark analyst-computed metrics as calculated and show the formula and inputs.

## Contents

- Canonical ledger codes
- Cross-subsector metrics
- Chip design / fabless
- IDM / foundry / OSAT
- Semiconductor equipment
- Semiconductor materials
- EDA / semiconductor IP
- Recommended semiconductor charts

## Canonical Ledger Codes

Use stable `metric` codes in `facts.csv`; keep the filing's original wording in
`source_line_item`. Add a disclosed scope after `:` when needed.

| Metric identity | Canonical code |
|---|---|
| Consolidated total/main-business/segment gross margin | `gross_margin_total`, `gross_margin_main_business`, `gross_margin_segment:<name>` |
| Total/parent/NCI/parent-ex-nonrecurring profit | `net_profit_total`, `net_profit_parent`, `net_profit_nci`, `net_profit_parent_ex_nonrecurring` |
| Product shipment or sales volume | `unit_volume:<reported product and unit>` |
| Same-scope calculated revenue per unit | `implied_revenue_per_unit:<reported product and unit>` |
| Operating/investing/financing/FX/cash change | `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `fx_effect_on_cash_and_equivalents`, `net_change_in_cash_and_equivalents` |
| PPE cash capex / broad long-term-assets cash line | `cash_paid_for_ppe`, `cash_paid_for_ppe_intangibles_and_other_long_term_assets` |
| Corresponding FCF variants | `free_cash_flow_ppe`, `free_cash_flow_long_term_assets` |
| Government support views | `government_grant_other_income`, `government_grant_nonoperating_income`, `government_grant_cost_offset`, `government_grant_nonrecurring`, `government_grant_deferred_balance`, `government_grant_cash_receipt` |
| Equipment order/shipment/installation/acceptance/revenue | `new_orders:<scope>`, `shipments:<scope>`, `installations:<scope>`, `acceptances:<scope>`, `recognized_revenue:<scope>` |
| Capacity states | `design_capacity:<unit>`, `installed_capacity:<unit>`, `qualified_capacity:<unit>`, `effective_output:<unit>`, `utilization_rate:<definition>` |

Do not force an unavailable fact to zero to make a chart complete. An observed
zero requires an explicit source row; an unavailable value uses
`status=unavailable`.

## Cross-Subsector Metrics

| Metric | Analysis purpose | Definition caution |
|---|---|---|
| Revenue by product/application/geography | Identify growth and concentration | Do not remap company segments without a reconciliation |
| Gross margin by segment/product | Assess mix, price, utilization, and cost | Often undisclosed; do not impute from peers |
| R&D expense / revenue | Assess innovation burden | Distinguish expense, total R&D investment, and capitalized development cost |
| Customer/supplier concentration | Assess dependency | Use the exact disclosed top-one/top-five basis and period |
| Inventory days | Assess cycle and obsolescence | Use average inventory when available; explain material acquisitions or reclassifications |
| DSO / receivable days | Assess collection and revenue quality | Include notes receivable/contract assets only when the selected formula says so |
| Capex and capex intensity | Assess investment burden | Use cash purchases of PPE unless another definition is stated; announced investment is not capex |
| Government support | Assess profit and funding dependence | Separate P&L grants, deferred-income amortization, tax incentives, and capital contributions |

## Chip Design / Fabless

Check when disclosed:

- unit shipments and shipment growth;
- ASP or calculated revenue per unit, only if revenue and comparable shipment units align;
- volume, price, product-mix, FX, and acquisition contributions;
- revenue by chip family, application, customer type, or geography;
- design wins, tape-outs, samples, customer validation, pilot delivery, and mass-production status;
- wafer process/node and foundry/packaging platform dependencies;
- wafer purchase commitments, capacity agreements, prepayments, take-or-pay obligations, and cancellation terms;
- NRE, IP license, royalty, and product revenue mix;
- inventory by raw materials/wafers, work in process, outsourced processing, finished goods, and channel stock when disclosed;
- inventory write-down rate, aging, returns, rebates, price protection, and distributor rights;
- R&D headcount, tape-out or project spending, and capitalized development cost.

Suggested calculations when inputs align:

- calculated ASP = relevant product revenue / comparable unit shipments;
- inventory days = average inventory / cost of sales x days in period;
- R&D ratio = R&D expense / revenue;
- purchase-commitment coverage = disclosed non-cancellable purchase commitments / relevant trailing cost base, with limitations stated.

Never infer current revenue from a design win or successful tape-out.

## IDM / Foundry / OSAT

Check when disclosed:

- wafer starts, wafer shipments, packaged/tested units, or equivalent output;
- monthly/annual capacity and whether it is design, installed, qualified, or effective capacity;
- utilization rate and its company definition;
- yield and ramp stage; never estimate undisclosed yield;
- ASP or revenue per wafer/unit where comparable;
- 8-inch/12-inch, process-node, specialty-platform, package, or application mix;
- advanced packaging capacity and revenue, without treating announced capacity as output;
- announced investment, cash capex, equipment prepayments, construction in progress, transfer to fixed assets, depreciation, and impairment;
- energy, utilities, consumables, substrates, wafers, and outsourced-service costs where disclosed;
- customer advances, long-term agreements, minimum purchase commitments, and pricing adjustments;
- government grants, tax incentives, subsidized loans, and project obligations.

Suggested bridges/calculations:

- calculated utilization only when actual output and compatible capacity definitions are disclosed;
- depreciation intensity = depreciation and amortization / revenue, with source scope stated;
- capex intensity = cash capex / revenue;
- construction-in-progress conversion = transfer from CIP to fixed assets / opening or average CIP, only when note data supports it;
- free cash flow = operating cash flow - cash capex, labeled calculated;
- incremental gross-margin bridge: price/mix, utilization, yield, input cost, and depreciation only to the extent quantified or source-stated.

## Semiconductor Equipment

Check when disclosed:

- new orders, firm orders, backlog, and book-to-bill;
- cancellation, rescheduling, framework-order, tax, and delivery-period definitions;
- systems shipped, installed, accepted, and recognized as revenue;
- product/system revenue versus service, spares, upgrades, and consumables;
- customer validation tools, demo tools, finished goods, goods shipped/not accepted, contract assets, and contract liabilities;
- acceptance cycle and revenue-recognition policy;
- customer fab-capex exposure and top-customer concentration;
- key component lead times, supplier concentration, import dependency, and export restrictions;
- warranty provisions, installation cost, service obligations, and field-support capacity.

Suggested calculations:

- book-to-bill = new orders / recognized revenue for the same scope and period;
- backlog coverage = period-end backlog / comparable trailing revenue;
- contract-liability coverage = contract liabilities / comparable trailing revenue;
- goods-shipped-not-accepted growth versus subsequent acceptance revenue, only when disclosed.

Do not treat framework agreements or gross order announcements as firm backlog unless the company does.

## Semiconductor Materials

Check when disclosed:

- sales volume, ASP, price changes, and product mix;
- design/installed/qualified capacity, production, sales, utilization, and yield;
- product purity/specification and financially relevant grade mix;
- customer qualification stage, approved supplier/line status, pilot supply, volume supply, and line/customer replication;
- raw-material, energy, logistics, and FX exposure plus contractual pass-through mechanisms;
- expansion completion, qualification, ramp, utilization, and depreciation;
- inventory aging, shelf life, contamination/quality risk, write-down, and return rights;
- customer and supplier concentration, import dependency, and geographic exposure.

Suggested calculations:

- sell-through ratio = sales volume / production volume, only for compatible product units;
- utilization = actual production / compatible effective capacity;
- calculated ASP = product revenue / comparable sales volume;
- raw-material pass-through lag only when contract or source data supports the timing.

Passing qualification is not equivalent to stable volume share.

## EDA / Semiconductor IP

Check when disclosed:

- ARR, subscription revenue, deferred revenue, remaining performance obligations, or backlog;
- renewal, retention, contract duration, and license type;
- term, perpetual, subscription, maintenance, project/NRE, usage-based, and royalty revenue;
- royalties linked to customer shipments and the reporting lag;
- customer concentration, foundry/process ecosystem support, and export-control exposure;
- capitalized software/development cost and acquired-intangible amortization.

Do not combine bookings, contract value, ARR, backlog, and recognized revenue without reconciling definitions.

## Recommended Semiconductor Charts

Use only available, traceable data:

- revenue growth decomposed into volume/price/mix when disclosed;
- revenue and margin by product/application/process/platform;
- inventory composition, days, and write-down rate;
- capex, CIP, fixed-asset additions, depreciation, utilization, and gross margin;
- orders, backlog, shipments, acceptance, revenue, and contract liabilities for equipment;
- capacity, production, sales, utilization, and qualification stage for manufacturing/materials;
- R&D expense, R&D ratio, and commercialization-stage pipeline;
- government support versus operating profit/net profit, with components kept separate.
