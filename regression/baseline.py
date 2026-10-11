"""Per-metric score baseline for regression gating.

The baseline is a JSON file mapping agent name -> scenario id -> metric
key -> score. A run regresses if any baselined score is lower now, or is
missing from the current run (so deleting a scenario or metric has to be
a deliberate baseline update). New scenarios and metrics are not
regressions; they enter the baseline on the next --update-baseline.
"""

import json
import os


def scores_from_results(results):
    """Turn evaluate_agent() results into {scenario_id: {metric_key: score}}."""
    return {
        r["id"]: {m["key"]: m["score"] for m in r["metrics"]} for r in results
    }


def save_baseline(path, all_results):
    """Write scores for every agent in [(agent_name, results), ...]."""
    baseline = {name: scores_from_results(results) for name, results in all_results}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(baseline, f, indent=2, sort_keys=True)
        f.write("\n")


def load_baseline(path):
    with open(path) as f:
        return json.load(f)


def find_regressions(baseline_scores, current_scores):
    """Return one message per (scenario, metric) whose score dropped or vanished."""
    regressions = []
    for scenario_id, metrics in sorted(baseline_scores.items()):
        current_metrics = current_scores.get(scenario_id, {})
        for metric_key, old_score in sorted(metrics.items()):
            new_score = current_metrics.get(metric_key)
            if new_score is None:
                regressions.append(
                    "%s / %s: %.1f -> missing" % (scenario_id, metric_key, old_score)
                )
            elif new_score < old_score:
                regressions.append(
                    "%s / %s: %.1f -> %.1f"
                    % (scenario_id, metric_key, old_score, new_score)
                )
    return regressions
