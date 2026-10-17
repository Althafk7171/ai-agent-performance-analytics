import copy
import json
import tempfile
import unittest
import contextlib
import io
import sqlite3
from pathlib import Path

import pipeline as p


def source(adapter="tau"):
    return dict(id="fixture", revision="fixture-revision", source_url="https://example.org/fixture",
                raw_sha256="fixture-hash", retrieved_at_utc="2026-10-06T00:00:00Z",
                variant="historical-airline", variants=["Verified"], agent_name="tool-calling",
                model_name="fixture-model", adapter=adapter)


def tau_entry(task=0, trial=0, reward=1):
    return dict(task_id=task, trial=trial, reward=reward, info={"user_cost": 0.02}, traj=[
        {"role": "assistant", "tool_calls": [{"function": {"name": "transfer_to_human_agents"}}]}])


class NormalizationTests(unittest.TestCase):
    def test_user_simulator_cost_is_not_agent_cost(self):
        results, runs = p.normalize_tau([tau_entry()], source())
        self.assertIsNone(runs[0]["agent_cost_usd"])
        self.assertEqual(runs[0]["user_simulator_cost_usd"], 0.02)
        self.assertIsNone(results[0]["avg_reported_task_cost_usd"])
        self.assertEqual(runs[0]["human_handoff_requested"], 1)

    def test_fractional_reward_fails_without_policy(self):
        with self.assertRaisesRegex(ValueError, "Fractional"):
            p.normalize_tau([tau_entry(reward=0.5)], source())

    def test_duplicate_trial_is_rejected(self):
        results, runs = p.normalize_tau([tau_entry(), tau_entry()], source())
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            p.validate(results, runs)

    def test_reliability_preserves_trial_denominator(self):
        _, runs = p.normalize_tau([tau_entry(), tau_entry(trial=1, reward=0)], source())
        row = p.reliability(runs)[0]
        self.assertEqual(row["observed_trials"], 2)
        self.assertEqual(row["empirical_success_rate"], 0.5)
        self.assertEqual(row["all_observed_trials_successful"], 0)

    def test_missing_cost_remains_null_and_percent_becomes_fraction(self):
        data = {"leaderboards": [{"name": "Verified", "results": [{"name": "fixture",
            "folder": "fixture-submission", "resolved": 80, "instance_cost": None,
            "per_instance_details": {"task-a": {"resolved": False, "cost": 0, "api_calls": 2}}}]}]}
        results, runs = p.normalize_swe(data, source("swe"))
        self.assertEqual(results[0]["success_rate"], 0.8)
        self.assertIsNone(results[0]["avg_reported_task_cost_usd"])
        self.assertEqual(runs[0]["agent_cost_usd"], 0)
        broken = copy.deepcopy(data)
        broken["leaderboards"][0]["results"][0]["resolved"] = 101
        with self.assertRaises(ValueError):
            p.normalize_swe(broken, source("swe"))

    def test_checksum_rejects_modified_raw_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw.json").write_text("[]", encoding="utf-8")
            manifest = {"schema_version": "1.0", "sources": [dict(source(), raw_file="raw.json")]}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                p.run(root / "manifest.json", root / "output")


class SnapshotIntegrationTests(unittest.TestCase):
    def test_offline_replay_and_sql_queries(self):
        manifests = sorted((p.ROOT / "data" / "raw").glob("*/manifest.json"))
        if not manifests:
            self.skipTest("No included snapshot")
        manifest = manifests[-1]
        manifest_data = p.load_json(manifest)
        hashes_before = {s["raw_file"]: p.digest((manifest.parent / s["raw_file"]).read_bytes())
                         for s in manifest_data["sources"]}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                p.run(manifest, out)
            for filename in ["benchmark_results.csv", "task_runs.csv", "task_reliability.csv"]:
                self.assertEqual((out / filename).read_bytes(),
                                 (p.ROOT / "data" / "processed" / filename).read_bytes())
            with contextlib.closing(sqlite3.connect(out / "analytics.sqlite")) as conn:
                self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                orphans = conn.execute('''SELECT COUNT(*) FROM task_runs t
                    LEFT JOIN benchmark_results b ON t.source_id=b.source_id
                      AND t.variant=b.variant AND t.submission_id=b.submission_id
                      AND t.raw_sha256=b.raw_sha256 WHERE b.record_id IS NULL''').fetchone()[0]
                self.assertEqual(orphans, 0)
                self.assertEqual(conn.execute('SELECT COUNT(latency_seconds) FROM task_runs').fetchone()[0], 0)
                queries = (p.ROOT / "sql" / "starter_analysis.sql").read_text(encoding="utf-8")
                queries = "\n".join(line for line in queries.splitlines()
                                    if not line.lstrip().startswith("--"))
                outputs = [conn.execute(query).fetchall() for query in queries.split(";") if query.strip()]
                self.assertTrue(all(outputs))
                self.assertEqual(len(outputs[-1]), 2)
                self.assertTrue(all(row[1] == 50 for row in outputs[-1]))
        for name, checksum in hashes_before.items():
            self.assertEqual(p.digest((manifest.parent / name).read_bytes()), checksum)


if __name__ == "__main__":
    unittest.main()
