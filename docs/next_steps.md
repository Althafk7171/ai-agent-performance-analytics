# Portfolio continuation

## Day 3 — SQL questions

Use the SQLite export and starter queries to answer:

1. Which submissions resolve the most tasks within each selected coding variant?
2. What is the performance–cost tradeoff among submissions with comparable settings
   and adequate cost coverage?
3. How often does a historical airline agent succeed on all four matched trials?
4. How do tool-call counts and requested handoffs differ between successful and
   unsuccessful airline trials? Describe associations, not causal explanations.

Check source settings before attributing a difference to the model. Keep available
task-row analysis distinct from published whole-benchmark rates.

## Day 4 — Excel exploration

Import the three CSV tables. Use pivot tables by benchmark, variant and submission.
Show sample counts and missing-data coverage. Format rates as percentages and costs
as currency. Check the quality report before creating charts. Avoid filling blank costs
or latency cells with zero.

## Day 5 onward — Power BI

Build three pages: coding performance, reported coding cost, historical airline reliability.
Add source/variant/settings filters and a visible provenance note. For reliability,
use the first four matched trials from starter SQL. Keep the full eight-trial Sonnet
sample available for a separate within-model exploration.

Suggested measures: published resolved fraction, observed run success fraction,
mean reported cost, spending per successful task within costed rows, cost coverage,
matched four-trial all-success fraction and requested handoff rate.

## Optional later enrichment

Collect fresh traces only as a separate, explicitly labeled experiment. Define run
configuration, prices and timestamps before measuring latency or tokens. If synthetic
business data is useful for demonstration, create a separate scenario table with
`is_simulated=1`, documented seed and assumptions; do not overwrite observed rows or
present scenario costs and ratings as benchmark measurements.

Portfolio description: “Built a reproducible Python ingestion pipeline for two public
AI-agent benchmark families, preserving source snapshots and preparing validated
performance, reported-cost and historical repeatability data for SQL and BI analysis.”
