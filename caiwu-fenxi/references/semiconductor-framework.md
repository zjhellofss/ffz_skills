# Semiconductor Financial Analysis Framework

Use this framework in addition to the general report framework whenever a company has a material semiconductor business. Apply only the subsector modules relevant to the company's actual business; do not force unavailable KPIs into the report.

## Contents

0. Complete the coverage matrix
1. Classify the business before comparing it
2. Map technology status to financial status
3. Apply the required industry analysis chain by subsector
4. Assess the semiconductor cycle
5. Add the required report sections
6. Apply peer-comparison rules

## 0. Complete the Coverage Matrix

Before drafting, mark each module `covered`, `not disclosed`, or `not material`
and link the relevant fact/claim IDs. Do not create repetitive empty chapters;
the matrix makes omissions explicit.

| Module | Status | Evidence / limitation |
|---|---|---|
| Value-chain position and revenue model |  |  |
| Product/process and commercialization map |  |  |
| Operating KPI bridge |  |  |
| Cycle, inventory, and capacity |  |  |
| Orders, qualification, acceptance, and revenue recognition |  |  |
| Capex, CIP, transfer, depreciation, and return |  |  |
| Supply chain, concentration, policy, and geography |  |  |

## 1. Classify the Business Before Comparing It

Classify each material revenue stream and explain how it makes money:

| Subsector | Typical business model | Primary financial drivers |
|---|---|---|
| Chip design / fabless | Design chips and outsource wafer fabrication and packaging | Shipments, ASP, mix, wafer and packaging cost, inventory, design wins |
| IDM | Design and manufacture chips | Product cycle, utilization, yield, capacity, depreciation, capex |
| Foundry | Manufacture wafers for customers | Wafer shipments, ASP, utilization, node/platform mix, depreciation |
| OSAT | Package and test chips | Volume, utilization, package mix, advanced-packaging capacity, depreciation |
| Equipment | Sell, install, and service production equipment | Orders, backlog, shipments, acceptance, service mix, customer capex |
| Materials | Supply wafers, gases, chemicals, targets, photoresist, masks, and related inputs | Volume, price, mix, qualification, capacity, yield, input cost |
| EDA / semiconductor IP | License software or IP and collect subscription, project, or royalty revenue | ARR/backlog, renewals, license mix, royalties, customer R&D activity |

For diversified companies, analyze each material model separately before consolidating conclusions. Do not present a blended margin or capex ratio as representative of every business.

## 2. Map Technology Status to Financial Status

Use the company's terminology but normalize disclosed product status into this ladder when possible:

`R&D -> tape-out/sample -> laboratory verification -> production-line/customer validation -> pilot/small-batch delivery -> mass production -> multi-customer or multi-line replication`

For equipment, use:

`R&D -> prototype -> customer-site verification -> shipment -> installation -> acceptance -> recognized revenue -> service/spares`

For every material new product or technology route, state:

- disclosed stage and reporting date;
- evidence of revenue, order, shipment, or customer acceptance;
- whether the item affects current revenue, future expectations, capex, inventory, or only R&D expense;
- what remains undisclosed.

Do not equate tape-out, sample delivery, validation, shipment, acceptance, and revenue recognition. Do not infer yield, technical superiority, customer identity, market share, or mass production from promotional wording.

## 3. Required Industry Analysis Chains

### Design / fabless

Analyze, when disclosed:

`revenue change -> shipment/volume + ASP/price + product mix + FX/acquisition`

Then connect demand and supply commitments to:

`design win/customer adoption -> wafer starts and purchase commitments -> work in process/inventory -> shipments -> receivables/cash collection -> inventory provisions or returns risk`

Explain foundry, packaging, IP, EDA, and capacity dependencies without naming undisclosed suppliers or customers.
When sales are mainly through distributors, keep billed-customer concentration
separate from end-customer/end-demand concentration. High foundry or supplier
concentration is not automatically a single-source dependency; verify
exclusivity and qualified alternatives.

### IDM / foundry / OSAT

Complete this bridge when data is available:

`announced investment -> cash capex/equipment prepayments -> construction in progress -> transfer to fixed assets -> depreciation -> installed/ramp capacity -> utilization and yield -> unit cost -> gross margin -> operating cash flow/free cash flow`

Distinguish design capacity, installed capacity, production capacity, qualified capacity, and effective output. Distinguish start of construction, equipment move-in, production start, and full ramp.
When NCI profit/loss is material, show total consolidated profit and
parent-attributable profit side by side. Do not assign NCI losses to a named fab
or expansion entity unless the filing provides that entity bridge.

### Equipment

Complete this bridge when disclosed:

`new orders -> cancellable/firm backlog -> production and inventory -> shipment -> installation -> customer acceptance -> revenue -> receivables/cash -> warranty and service obligation`

Explain the company's revenue-recognition trigger. Treat shipments, installed units, accepted units, and recognized revenue as separate measures unless the filing explicitly aligns them.

### Materials

Complete this bridge when disclosed:

`sample -> qualification -> supplier code/approved line -> pilot supply -> volume supply -> additional customer/line replication`

Connect expansion to capacity, qualification, utilization, yield, unit cost, inventory shelf life, and cash return. A completed plant is not necessarily qualified or economically utilized capacity.

### EDA / IP

Separate subscription, term license, perpetual license, project/NRE, maintenance, usage-based, and royalty revenue. Explain timing, renewal exposure, concentration, deferred revenue or contract liabilities, and the relationship between customer tape-outs/shipments and royalty recognition when disclosed.

## 4. Semiconductor Cycle Assessment

Do not rely on one YoY comparison. Use several periods when available and assess:

- end-demand cycle by disclosed application;
- customer and channel inventory cycle;
- wafer capacity and utilization cycle;
- memory or commodity price cycle where relevant;
- customer fab-capex cycle for equipment and materials;
- product replacement and design-win cycle;
- capacity construction, qualification, and ramp cycle.

Classify growth drivers only when evidence supports the distinction:

- cyclical recovery or inventory normalization;
- structural market-share gain or localization;
- volume, price, or product-mix change;
- acquisition, disposal, FX, or reporting-scope change;
- new-capacity contribution;
- low-base effect.

If industry data is used, cite an authoritative current source and keep it separate from company-reported figures.

## 5. Required Report Additions

Add these subsections to the general report when material:

1. `Semiconductor value-chain position and revenue model`
2. `Product, process, and commercialization-stage map`
3. `Operating KPI bridge` using applicable metrics only
4. `Cycle, inventory, and capacity assessment`
5. `Orders, qualification, and revenue-recognition quality`
6. `Capex, transfer-to-fixed-assets, depreciation, and return assessment`
7. `Supply-chain, customer-concentration, policy, and geographic exposure`

For each KPI, preserve the company's definition and unit. State `not disclosed` instead of estimating utilization, yield, ASP, backlog, market share, or customer identity.

## 6. Peer Comparison Rules

Before comparing peers, confirm:

- same or closely related subsector and revenue model;
- similar product/application mix and manufacturing intensity;
- comparable reporting periods and accounting standards;
- consistent definitions for capacity, utilization, shipment, order, backlog, R&D, subsidy, and non-GAAP metrics;
- organic versus acquisition-driven growth is separated;
- revenue recognition occurs at a comparable fulfillment point.

Do not use fabless capex intensity as a benchmark for IDM/foundry, equipment gross margin as a benchmark for component suppliers, or memory inventory cycles as a benchmark for analog products without explaining why the comparison is useful.
