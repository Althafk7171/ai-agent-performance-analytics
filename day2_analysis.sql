CREATE DATABASE IF NOT EXISTS ai_agent_analytics;
USE ai_agent_analytics;

SELECT DATABASE() AS current_database;

USE ai_agent_analytics;

SELECT COUNT(*) AS imported_rows
FROM benchmark_results_raw;

SELECT agent_name, model_name, variant,
       success_rate, avg_reported_task_cost_usd
FROM benchmark_results_raw
LIMIT 5;


-- Check row count and duplicate IDs.
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT record_id) AS unique_ids
FROM benchmark_results_raw;

-- Count missing or empty metric values.
SELECT
    SUM(CASE
        WHEN NULLIF(TRIM(success_rate), '') IS NULL
        THEN 1 ELSE 0
    END) AS missing_success_rates,
    SUM(CASE
        WHEN NULLIF(TRIM(avg_reported_task_cost_usd), '') IS NULL
        THEN 1 ELSE 0
    END) AS missing_costs
FROM benchmark_results_raw;

-- Count submissions and available costs by benchmark group.
SELECT
    benchmark,
    variant,
    COUNT(*) AS submissions,
    SUM(CASE
        WHEN NULLIF(TRIM(avg_reported_task_cost_usd), '') IS NOT NULL
        THEN 1 ELSE 0
    END) AS submissions_with_cost
FROM ai_agent_analytics.benchmark_results_raw
GROUP BY benchmark, variant
ORDER BY benchmark, variant;

-- Find nonnumeric values before converting text to numbers.
SELECT record_id, success_rate, avg_reported_task_cost_usd
FROM ai_agent_analytics.benchmark_results_raw
WHERE TRIM(success_rate) NOT REGEXP '^[0-9]+([.][0-9]+)?$'
   OR (
       NULLIF(TRIM(avg_reported_task_cost_usd), '') IS NOT NULL
       AND TRIM(avg_reported_task_cost_usd)
           NOT REGEXP '^[0-9]+([.][0-9]+)?$'
   );
   
USE ai_agent_analytics;

CREATE VIEW benchmark_results_clean AS
SELECT
    record_id,
    benchmark,
    variant,
    submission_id,
    agent_name,
    model_name,
    CAST(TRIM(success_rate) AS DECIMAL(9,6))
        AS success_rate,
    CAST(
        NULLIF(TRIM(avg_reported_task_cost_usd), '')
        AS DECIMAL(18,6)
    ) AS avg_reported_task_cost_usd,
    warning,
    tags_json
FROM benchmark_results_raw;

SELECT
    COUNT(*) AS total_rows,
    COUNT(avg_reported_task_cost_usd) AS rows_with_cost
FROM benchmark_results_clean;

SELECT
    submission_id,
    agent_name,
    model_name,
    ROUND(success_rate * 100, 1) AS success_rate_pct,
    ROUND(avg_reported_task_cost_usd, 3) AS avg_task_cost_usd
FROM ai_agent_analytics.benchmark_results_clean
WHERE benchmark = 'SWE-bench'
  AND variant = 'Verified'
  AND NULLIF(TRIM(warning), '') IS NULL
ORDER BY success_rate DESC, submission_id
LIMIT 10;

SELECT
    submission_id,
    agent_name,
    model_name,
    ROUND(success_rate * 100, 1) AS success_rate_pct,
    ROUND(avg_reported_task_cost_usd, 3) AS avg_task_cost_usd
FROM ai_agent_analytics.benchmark_results_clean
WHERE benchmark = 'SWE-bench'
  AND variant = 'Verified'
  AND NULLIF(TRIM(warning), '') IS NULL
  AND avg_reported_task_cost_usd IS NOT NULL
ORDER BY success_rate DESC, submission_id
LIMIT 10;

SELECT
    COUNT(*) AS total_submissions,
    COUNT(avg_reported_task_cost_usd) AS submissions_with_cost,
    COUNT(*) - COUNT(avg_reported_task_cost_usd)
        AS submissions_missing_cost,
    ROUND(
        100.0 * COUNT(avg_reported_task_cost_usd)
        / NULLIF(COUNT(*), 0), 1
    ) AS cost_coverage_pct
FROM ai_agent_analytics.benchmark_results_clean
WHERE benchmark = 'SWE-bench'
  AND variant = 'Verified'
  AND NULLIF(TRIM(warning), '') IS NULL;
  
SELECT
    submission_id,
    agent_name,
    model_name,
    variant,
    success_rate,
    avg_reported_task_cost_usd,
    tags_json
FROM ai_agent_analytics.benchmark_results_clean
WHERE benchmark = 'SWE-bench'
  AND variant = 'Verified'
  AND NULLIF(TRIM(warning), '') IS NULL
ORDER BY success_rate DESC, submission_id;

USE ai_agent_analytics;

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT record_id) AS unique_ids
FROM task_runs_raw;

SELECT
    source_id,
    COUNT(*) AS trial_rows,
    COUNT(DISTINCT task_id) AS unique_tasks
FROM task_runs_raw
WHERE benchmark = 'tau-bench'
GROUP BY source_id;

SELECT benchmark, source_id, COUNT(*) AS imported_rows
FROM ai_agent_analytics.task_runs_raw
GROUP BY benchmark, source_id;

SHOW COLUMNS FROM ai_agent_analytics.task_runs_raw;

USE ai_agent_analytics;

CREATE TABLE task_runs_staging LIKE task_runs_raw;

ALTER TABLE task_runs_staging
    MODIFY COLUMN success TEXT,
    MODIFY COLUMN agent_cost_usd TEXT,
    MODIFY COLUMN api_calls TEXT,
    MODIFY COLUMN is_simulated TEXT;
    
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT record_id) AS unique_ids
FROM ai_agent_analytics.task_runs_staging;

SELECT benchmark, source_id, COUNT(*) AS imported_rows
FROM ai_agent_analytics.task_runs_staging
GROUP BY benchmark, source_id;

USE ai_agent_analytics;

-- Summarize four trials for each agent and task.
CREATE VIEW tau_four_trial_tasks AS
SELECT
    source_id,
    agent_name,
    model_name,
    task_id,
    SUM(CAST(success AS UNSIGNED)) AS successful_trials
FROM task_runs_staging
WHERE benchmark = 'tau-bench'
  AND TRIM(trial_index) IN ('0', '1', '2', '3')
GROUP BY source_id, agent_name, model_name, task_id
HAVING COUNT(*) = 4
   AND COUNT(DISTINCT trial_index) = 4;

-- Compare tasks present for both agents.
SELECT
    source_id,
    model_name,
    COUNT(*) AS matched_tasks,
    ROUND(AVG(successful_trials / 4.0) * 100, 1)
        AS trial_success_pct,
    ROUND(
        AVG(CASE WHEN successful_trials = 4 THEN 1.0 ELSE 0.0 END)
        * 100, 1
    ) AS all_four_success_pct
FROM tau_four_trial_tasks
WHERE task_id IN (
    SELECT task_id
    FROM tau_four_trial_tasks
    GROUP BY task_id
    HAVING COUNT(DISTINCT source_id) = 2
)
GROUP BY source_id, model_name;