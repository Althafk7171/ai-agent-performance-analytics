# Data provenance and interpretation

## Pinned sources

Collected on 6 October 2026. Each raw manifest records its exact retrieval timestamp,
URL, Git revision, byte count, JSON SHA-256 and license SHA-256. The registry is in
`config/sources.json`. Each normalized row carries the originating snapshot hash and URL.

| Family | Revision | Files |
| --- | --- | --- |
| SWE-bench | `193160a463a435d05cf44a1fa9dc5eac832113c3` | `data/leaderboards.json` |
| τ-bench | `59a200c6d575d595120f1cb70fea53cef0632f6b` | `historical_trajectories/gpt-4o-airline.json`, `historical_trajectories/sonnet-35-new-airline.json` |

SWE-bench's repository LICENSE is **CC BY-NC 4.0**; Sierra's repository LICENSE is
**MIT**. Exact upstream license texts are included beside raw JSON; retain those
notices and source attribution when sharing portfolio data. The collected source is
public benchmark material; this project makes no claim to own its upstream content.

## Why these sources

SWE-bench supplies coding evaluation data in structured form. Only Verified and
Multilingual are selected for the initial analysis. Task details are available for a
subset of submissions; summary entries remain even when details or costs are missing.
The data includes different agents and settings, preserved in `tags_json` and identifiers.

τ-bench contributes repeated airline task trajectories. The
[upstream README](https://github.com/sierra-research/tau-bench/blob/59a200c6d575d595120f1cb70fea53cef0632f6b/README.md)
labels these tasks outdated and directs new evaluations to its successor repository.
They are suitable for historical reliability analysis and pipeline practice, not a
claim about the current strongest agent. Filename model labels are retained; exact
provider model versions and generation dates are not inferred. The tool-calling strategy
label comes from upstream historical trajectory context, rather than a per-run metadata field.

The included GPT-4o file has 50 tasks with four trials each; the Sonnet file has 50
tasks with eight trials each. Their full-sample all-trials-success rates are not directly
comparable. Starter SQL restricts both to matching tasks and trial indices 0–3.

## Observed, derived and missing

| Category | Fields and rules |
| --- | --- |
| Upstream reported | SWE `resolved`, `instance_cost`, `per_instance_details.resolved/cost/api_calls`, date, agent/model labels, checked flag, tags and warnings; τ task ID, trial, reward, simulator cost and messages |
| Derived | Stable record IDs; SWE percentage divided by 100; binary success from τ reward equal to 1; counts of assistant tool calls; presence of `transfer_to_human_agents`; τ trial success means; task-level trial counts and all-observed-trials success |
| Curated metadata | Benchmark/domain labels, chosen scope, τ filename model labels and strategy context, `is_simulated=0` |
| Missing | Latency, token usage, τ agent cost, SWE trial indices and tool-call counts; business departments, user ratings and difficulty labels are not created |
| Simulated enrichment | **None added.** τ's benchmark itself uses simulated users. Its published agent outcomes are observed benchmark data, not newly simulated portfolio records. |

Cost columns preserve upstream reported dollar values as USD. They are source estimates,
not audited bills or costs recomputed at 2026 prices. SWE task cost maps to `cost`, and
summary average task cost maps to `instance_cost`; no total-cost estimate is manufactured.
τ `info.user_cost` is the **user simulator's** cost and must never be called agent cost.
Its historical files do not supply agent cost. A handoff request is a tool-call event,
not measured human intervention or a successfully completed human transfer.

Task detail success rates may differ from rounded published summary percentages and
may cover fewer records. Summary evaluated counts stay NULL for SWE instead of assuming
a denominator from the nominal benchmark size. τ evaluated counts are derived from the
actual included run rows. Every reward must be binary; a future fractional reward fails
validation until a policy is chosen.

## Analytical boundaries

- Benchmark outcomes measure their particular scoring rules, not general business quality.
- Report success within a benchmark, variant, submission and snapshot. API calls and tool
  calls are distinct metrics; API calls are not a task-complexity label.
- Task reliability is an empirical summary of observed repeats. It is not the benchmark's
  official pass^k estimator and does not establish production failure probabilities.
- Report cost coverage and sample size alongside cost charts. Unsuccessful tasks consume
  cost too; include that spending when calculating spending per successful task.
- Preserve NULLs. The absence of latency data means no latency analysis is supportable yet.
- Raw trajectories contain fictional benchmark customer scenarios; the clean CSV exports
  omit conversation content and customer profiles.
