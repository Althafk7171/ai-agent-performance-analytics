-- SQLite syntax; CSV exports can also be imported into SQL Server/PostgreSQL.
-- Keep benchmark, variant, submission and snapshot context in every comparison.

-- Published coding performance, including missing cost values.
SELECT variant, submission_id, agent_name, model_name, success_rate,
       avg_reported_task_cost_usd, upstream_checked, tags_json
FROM benchmark_results
WHERE benchmark = 'SWE-bench' AND (warning IS NULL OR warning = '')
ORDER BY variant, success_rate DESC;

-- Cost analysis over the AVAILABLE task-level records (may be a subset).
-- Spending on failures is included. NULL costs never become zero.
SELECT benchmark, variant, submission_id,
       COUNT(*) AS available_task_rows,
       SUM(CASE WHEN agent_cost_usd IS NOT NULL THEN 1 ELSE 0 END) AS costed_rows,
       AVG(success * 1.0) AS available_task_success_rate,
       AVG(agent_cost_usd) AS mean_reported_cost_usd,
       SUM(agent_cost_usd) / NULLIF(SUM(CASE WHEN agent_cost_usd IS NOT NULL
                                               THEN success ELSE 0 END), 0)
           AS spending_per_success_in_costed_subset_usd
FROM task_runs
WHERE benchmark = 'SWE-bench'
GROUP BY benchmark, variant, submission_id;

-- Compare historical tau models over the same first four trial indices.
-- all_four_successful_fraction is an empirical observation, not official pass^k.
WITH matched_tasks AS (
    SELECT task_id FROM task_runs
    WHERE benchmark = 'tau-bench' AND trial_index BETWEEN 0 AND 3
    GROUP BY task_id
    HAVING COUNT(DISTINCT submission_id) = 2 AND COUNT(*) = 8
), four_trial_tasks AS (
    SELECT submission_id, task_id, COUNT(*) AS trials, SUM(success) AS successes
    FROM task_runs
    WHERE benchmark = 'tau-bench' AND trial_index BETWEEN 0 AND 3
      AND task_id IN (SELECT task_id FROM matched_tasks)
    GROUP BY submission_id, task_id
    HAVING COUNT(*) = 4
)
SELECT submission_id, COUNT(*) AS matched_tasks,
       AVG(successes / 4.0) AS first_four_trial_success_rate,
       AVG(CASE WHEN successes = 4 THEN 1.0 ELSE 0.0 END) AS all_four_successful_fraction
FROM four_trial_tasks
GROUP BY submission_id;
