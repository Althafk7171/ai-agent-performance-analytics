"""Small, dependency-free benchmark pipeline. Run from any working directory."""
import argparse
import csv
import hashlib
import json
import math
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMON = ["record_id", "source_id", "benchmark", "variant", "submission_id", "agent_name",
          "model_name", "domain", "source_url", "source_revision", "raw_sha256", "retrieved_at_utc"]
RESULT_FIELDS = COMMON + ["submission_date", "metric_name", "success_rate", "success_rate_origin",
    "evaluated_runs", "unique_tasks", "avg_reported_task_cost_usd", "cost_origin", "warning",
    "upstream_checked", "tags_json", "is_simulated"]
RUN_FIELDS = COMMON + ["task_id", "trial_index", "success", "reported_reward", "agent_cost_usd",
    "user_simulator_cost_usd", "api_calls", "tool_calls", "human_handoff_requested",
    "latency_seconds", "input_tokens", "output_tokens", "is_simulated"]
RELIABILITY_FIELDS = ["source_id", "benchmark", "variant", "submission_id", "task_id",
    "observed_trials", "successful_trials", "empirical_success_rate", "all_observed_trials_successful",
    "raw_sha256", "is_simulated"]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def number(value, label, low=0, high=None, integer=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: expected numeric value, got {value!r}")
    if not math.isfinite(value) or value < low or (high is not None and value > high):
        raise ValueError(f"{label}: out of range: {value}")
    if integer and int(value) != value:
        raise ValueError(f"{label}: expected integer")
    return int(value) if integer else value


def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "portfolio-benchmark-etl/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def download(config):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = ROOT / "data" / "raw" / stamp
    destination.mkdir(parents=True)
    manifest = {"schema_version": config["schema_version"], "sources": []}
    for source in config["sources"]:
        base = f"https://raw.githubusercontent.com/{source['repository']}/{source['revision']}/"
        url = base + source["path"]
        print(f"Downloading {source['id']} ...", flush=True)
        payload = fetch(url)
        json.loads(payload)  # Don't accept an HTML error page as raw JSON.
        name = source["id"] + ".json"
        (destination / name).write_bytes(payload)
        repo_slug = source["repository"].replace("/", "__")
        license_name = repo_slug + "__LICENSE.txt"
        if not (destination / license_name).exists():
            (destination / license_name).write_bytes(fetch(base + "LICENSE"))
        entry = dict(source, source_url=url, raw_file=name, raw_sha256=digest(payload),
                     retrieved_at_utc=datetime.now(timezone.utc).isoformat(), bytes=len(payload),
                     license_file=license_name,
                     license_sha256=digest((destination / license_name).read_bytes()))
        manifest["sources"].append(entry)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return destination / "manifest.json"


def base_row(source, benchmark, variant, submission, agent, model, domain):
    return dict(source_id=source["id"], benchmark=benchmark, variant=variant,
                submission_id=submission, agent_name=agent, model_name=model, domain=domain,
                **{k: source[k] for k in ["source_url", "raw_sha256", "retrieved_at_utc"]},
                source_revision=source["revision"], is_simulated=0)


def record_id(*parts):
    return digest(json.dumps(parts, ensure_ascii=False).encode())[:24]


def normalize_swe(data, source):
    results, runs = [], []
    boards = data["leaderboards"]
    names = {b["name"] for b in boards}
    if set(source["variants"]) - names:
        raise ValueError("Configured SWE-bench variant missing from upstream")
    for board in boards:
        variant = board["name"]
        if variant not in source["variants"]:
            continue
        for item in board["results"]:
            submission = item["folder"]
            common = base_row(source, "SWE-bench", variant, submission,
                              item.get("agent") or item["name"], item.get("model_display"), "coding")
            rate = number(item["resolved"], "resolved percentage", high=100) / 100
            cost = number(item.get("instance_cost"), "instance cost")
            results.append(dict(common, record_id=record_id(source["id"], variant, submission),
                submission_date=item.get("date"), metric_name="resolved_fraction",
                success_rate=rate, success_rate_origin="reported_percentage_divided_by_100",
                evaluated_runs=None, unique_tasks=None, avg_reported_task_cost_usd=cost,
                cost_origin="reported_instance_cost" if cost is not None else "missing",
                warning=item.get("warning"), upstream_checked=item.get("checked"),
                tags_json=json.dumps(item.get("tags", []), ensure_ascii=False)))
            for task, detail in item.get("per_instance_details", {}).items():
                if type(detail["resolved"]) is not bool:
                    raise ValueError("Task resolved must be a boolean")
                runs.append(dict(common, record_id=record_id(source["id"], variant, submission, task),
                    task_id=task, trial_index=None, success=int(detail["resolved"]),
                    reported_reward=None, agent_cost_usd=number(detail.get("cost"), "task cost"),
                    user_simulator_cost_usd=None,
                    api_calls=number(detail.get("api_calls"), "API calls", integer=True),
                    tool_calls=None, human_handoff_requested=None,
                    latency_seconds=None, input_tokens=None, output_tokens=None))
    return results, runs


def normalize_tau(data, source):
    if not isinstance(data, list) or not data:
        raise ValueError("Tau source must be a nonempty list")
    common = base_row(source, "tau-bench", source["variant"], source["id"],
                      source["agent_name"], source["model_name"], "airline")
    runs = []
    for entry in data:
        task = number(entry["task_id"], "task ID", integer=True)
        trial = number(entry["trial"], "trial index", integer=True)
        reward = number(entry["reward"], "reward", high=1)
        if reward not in (0, 1):
            raise ValueError("Fractional reward needs an explicit success policy")
        info = entry["info"]
        tool_names = [call["function"]["name"] for message in entry["traj"]
                      if message.get("role") == "assistant"
                      for call in (message.get("tool_calls") or [])]
        runs.append(dict(common, record_id=record_id(source["id"], task, trial),
            task_id=str(task), trial_index=trial, success=int(reward == 1), reported_reward=reward,
            agent_cost_usd=None, user_simulator_cost_usd=number(info.get("user_cost"), "user cost"),
            api_calls=None, tool_calls=len(tool_names),
            human_handoff_requested=int("transfer_to_human_agents" in tool_names),
            latency_seconds=None, input_tokens=None, output_tokens=None))
    results = [dict(common, record_id=record_id(source["id"], "aggregate"), submission_date=None,
        metric_name="observed_trial_success_fraction",
        success_rate=sum(r["success"] for r in runs) / len(runs),
        success_rate_origin="derived_mean_of_observed_binary_rewards", evaluated_runs=len(runs),
        unique_tasks=len({r["task_id"] for r in runs}), avg_reported_task_cost_usd=None,
        cost_origin="missing_agent_cost_user_simulator_cost_is_separate",
        warning="Historical tasks; upstream recommends newer tau benchmark versions",
        upstream_checked=None, tags_json="[]")]
    return results, runs


def reliability(runs):
    groups = defaultdict(list)
    for run in runs:
        if run["benchmark"] == "tau-bench":
            groups[(run["source_id"], run["variant"], run["submission_id"], run["task_id"])].append(run)
    rows = []
    for (source, variant, submission, task), trials in sorted(groups.items()):
        n = len(trials)
        successes = sum(t["success"] for t in trials)
        rows.append(dict(source_id=source, benchmark="tau-bench", variant=variant,
            submission_id=submission, task_id=task, observed_trials=n, successful_trials=successes,
            empirical_success_rate=successes / n, all_observed_trials_successful=int(successes == n),
            raw_sha256=trials[0]["raw_sha256"], is_simulated=0))
    return rows


def validate(results, runs):
    if not results or not runs:
        raise ValueError("No normalized records")
    for label, rows in [("results", results), ("runs", runs)]:
        ids = [r["record_id"] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate {label} record IDs")
        for row in rows:
            if not row["submission_id"] or row["is_simulated"] != 0:
                raise ValueError("Missing submission or unexpected simulation")
            if label == "results":
                number(row["success_rate"], "success rate", high=1)
            elif row["success"] not in (0, 1):
                raise ValueError("Invalid binary success")


def write_csv(path, fields, rows):
    # UTF-8 BOM helps Excel recognize Unicode; None becomes an empty cell.
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_database(path, tables):
    # Replace tables inside a transaction, preserving proper SQL NULL values.
    integer_fields = {"success", "trial_index", "api_calls", "tool_calls", "human_handoff_requested",
        "input_tokens", "output_tokens", "is_simulated", "evaluated_runs", "unique_tasks",
        "upstream_checked", "observed_trials", "successful_trials", "all_observed_trials_successful"}
    real_fields = {"success_rate", "reported_reward", "avg_reported_task_cost_usd", "agent_cost_usd",
        "user_simulator_cost_usd", "latency_seconds", "empirical_success_rate"}
    with closing(sqlite3.connect(path)) as conn, conn:
        for name, fields, rows in tables:
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')
            definition = ", ".join(f'"{f}" {"INTEGER" if f in integer_fields else "REAL" if f in real_fields else "TEXT"}'
                                   for f in fields)
            conn.execute(f'CREATE TABLE "{name}" ({definition})')
            placeholders = ",".join("?" for _ in fields)
            conn.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})',
                             [[r.get(f) for f in fields] for r in rows])
        for name in ["benchmark_results", "task_runs"]:
            conn.execute(f'CREATE UNIQUE INDEX "{name}_record_id" ON "{name}" (record_id)')


def run(manifest_path, out):
    manifest = load_json(manifest_path)
    if manifest["schema_version"] != "1.0":
        raise ValueError("Unsupported schema version")
    results, runs = [], []
    for source in manifest["sources"]:
        raw_path = (manifest_path.parent / source["raw_file"]).resolve()
        if not raw_path.is_relative_to(manifest_path.parent.resolve()):
            raise ValueError("Raw file escapes manifest directory")
        payload = raw_path.read_bytes()
        if digest(payload) != source["raw_sha256"]:
            raise ValueError(f"Raw checksum mismatch: {source['id']}")
        adapter = {"swe": normalize_swe, "tau": normalize_tau}[source["adapter"]]
        source_results, source_runs = adapter(json.loads(payload), source)
        results.extend(source_results)
        runs.extend(source_runs)
    results.sort(key=lambda r: r["record_id"])
    runs.sort(key=lambda r: r["record_id"])
    validate(results, runs)
    reliability_rows = reliability(runs)
    out.mkdir(parents=True, exist_ok=True)
    tables = [("benchmark_results", RESULT_FIELDS, results), ("task_runs", RUN_FIELDS, runs),
              ("task_reliability", RELIABILITY_FIELDS, reliability_rows)]
    for name, fields, rows in tables:
        write_csv(out / (name + ".csv"), fields, rows)
    write_database(out / "analytics.sqlite", tables)
    report = {"schema_version": "1.0", "manifest": str(manifest_path.resolve()),
        "row_counts": {name: len(rows) for name, _, rows in tables},
        "task_runs_by_source": dict(Counter(r["source_id"] for r in runs)),
        "task_runs_with_agent_cost": sum(r["agent_cost_usd"] is not None for r in runs),
        "task_runs_with_latency": sum(r["latency_seconds"] is not None for r in runs),
        "results_with_warnings": sum(bool(r["warning"]) for r in results),
        "simulated_rows": 0, "checks": {"raw_checksums": "passed", "unique_record_ids": "passed",
        "numeric_ranges": "passed", "simulation_flag": "passed"},
        "tau_trial_count_distribution": dict(Counter(r["observed_trials"] for r in reliability_rows))}
    (out / "quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download pinned upstream files")
    parser.add_argument("--manifest", type=Path, help="Replay an existing snapshot without network")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args()
    if args.refresh and args.manifest:
        parser.error("Choose --refresh or --manifest")
    if args.refresh:
        manifest = download(load_json(ROOT / "config" / "sources.json"))
    elif args.manifest:
        manifest = args.manifest.resolve()
    else:
        snapshots = sorted((ROOT / "data" / "raw").glob("*/manifest.json"))
        if not snapshots:
            parser.error("No snapshot found; run with --refresh first")
        manifest = snapshots[-1]
    run(manifest, args.output.resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, urllib.error.URLError) as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        sys.exit(1)
