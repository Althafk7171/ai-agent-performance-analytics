# Common schema — version 1.0

CSV empty cells and SQLite NULL both mean unavailable. Rates are fractions between 0
and 1. Flags are 0/1 (NULL when unavailable); counts are nonnegative integers. Dates are
ISO dates, retrieval timestamps are UTC ISO timestamps. Costs use decimal USD values.

## Shared provenance and identifiers

These fields appear in `benchmark_results` and `task_runs`.

| Column | Type | Meaning |
| --- | --- | --- |
| record_id | text | 24-character SHA-256-derived key for source, variant/submission and row grain; unique within a snapshot table |
| source_id | text | Source registry identifier |
| benchmark | text | `SWE-bench` or `tau-bench` |
| variant | text | Verified, Multilingual or historical-airline; never mix silently |
| submission_id | text | SWE upstream folder; τ source file ID |
| agent_name | text | Upstream SWE agent/name; τ tool-calling context label |
| model_name | text/null | SWE display label; τ upstream filename label |
| domain | text | Curated coding or airline label |
| source_url | text | Pinned raw download URL |
| source_revision | text | Upstream Git commit SHA |
| raw_sha256 | text | SHA-256 of original source JSON bytes |
| retrieved_at_utc | timestamp | Collection timestamp, not execution time |
| is_simulated | integer | Always 0; no synthetic portfolio rows were added |

Keys identify logical records across refreshes. For longitudinal storage, use
`(record_id, raw_sha256, retrieved_at_utc)` as snapshot context rather than treating a
refresh as another agent trial. The current exports contain only one manifest at a time.

## benchmark_results.csv

**Grain:** one SWE submission × variant, or one τ source-file aggregate.

| Additional column | Type | Meaning |
| --- | --- | --- |
| submission_date | date/null | Reported SWE submission date; unavailable for τ |
| metric_name | text | resolved_fraction or observed_trial_success_fraction |
| success_rate | real | Reported resolved percentage / 100, or mean of included τ binary rewards |
| success_rate_origin | text | Exact derivation label |
| evaluated_runs | integer/null | Included τ run count; SWE denominator left unavailable |
| unique_tasks | integer/null | Included τ distinct tasks; SWE summary count left unavailable |
| avg_reported_task_cost_usd | real/null | SWE instance_cost; no substitution from simulator cost |
| cost_origin | text | reported_instance_cost or explanatory missing-value label |
| warning | text/null | Upstream warning, or historical τ caveat |
| upstream_checked | integer/null | SWE checked field; not a portfolio quality certification |
| tags_json | text | JSON array preserving SWE model, system and settings tags |

## task_runs.csv

**Grain:** one available SWE per-instance result × submission × variant, or one τ task × trial.
There is no attempt count inferred for SWE: its per-instance outcome is whatever that
submission reported under its recorded settings.

| Additional column | Type | Meaning |
| --- | --- | --- |
| task_id | text | Benchmark-local instance/task ID |
| trial_index | integer/null | τ upstream zero-based trial index; unavailable for SWE |
| success | integer | SWE resolved boolean; τ reward == 1 |
| reported_reward | real/null | τ raw reward, constrained to 0 or 1 |
| agent_cost_usd | real/null | SWE reported per-instance cost; unavailable for τ |
| user_simulator_cost_usd | real/null | τ info.user_cost; separate expense category |
| api_calls | integer/null | SWE reported api_calls; not inferred from messages |
| tool_calls | integer/null | Count of τ assistant tool_calls entries |
| human_handoff_requested | integer/null | τ transfer_to_human_agents appears at least once |
| latency_seconds | real/null | Reserved; no current source provides it |
| input_tokens / output_tokens | integer/null | Reserved; currently unavailable |

## task_reliability.csv

**Grain:** one τ task × source/submission. Fields `source_id`, `benchmark`, `variant`,
`submission_id`, `task_id`, `raw_sha256`, `is_simulated` retain their meanings above.

| Additional column | Type | Meaning |
| --- | --- | --- |
| observed_trials | integer | Number of unique observed trial records |
| successful_trials | integer | Sum of binary success |
| empirical_success_rate | real | successful_trials / observed_trials |
| all_observed_trials_successful | integer | 1 only when every included trial succeeded |

No relationship should use model_name alone. Join task data to summaries on
`source_id + variant + submission_id + raw_sha256`. SWE summary rows without task data
must remain visible via left joins. Power BI can create a submission dimension with
these four fields and a combined key for one-to-many relationships.
