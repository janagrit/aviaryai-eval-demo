#!/usr/bin/env python3
"""Run the adversarial evaluation harness and write a Markdown report.

Evaluates both agent configurations (strict and lax) against every
adversarial scenario, scores each reply with the deterministic DeepEval
metrics, and writes report/eval_report.md. Fully offline, no API keys.

Exits non-zero if any Strict Agent score drops below the saved baseline
(regression/baseline_scores.json). Use --update-baseline to accept the
current scores as the new baseline.
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deepeval.test_case import LLMTestCase

from agent.mock_voice_agent import MockVoiceAgent
from metrics.custom_metrics import METRIC_REGISTRY
from regression.baseline import find_regressions, load_baseline, save_baseline, scores_from_results
from tests.test_adversarial import SCENARIOS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE_DIR, "report", "eval_report.md")
BASELINE_PATH = os.path.join(BASE_DIR, "regression", "baseline_scores.json")
AGENT_MODES = ("strict", "lax")
# Only the production-candidate agent is gated; the lax agent is a foil.
GATED_AGENT = "Strict Agent"


def evaluate_agent(mode):
    """Run all scenarios against one agent config. Returns (name, results)."""
    agent = MockVoiceAgent(mode=mode)
    results = []
    for scenario in SCENARIOS:
        reply = agent.respond(scenario["user_input"])
        test_case = LLMTestCase(
            input=scenario["user_input"],
            actual_output=reply,
        )
        metric_results = []
        for metric_name in scenario["metrics"]:
            metric = METRIC_REGISTRY[metric_name]()
            score = metric.measure(test_case)
            metric_results.append(
                {
                    "key": metric_name,
                    "name": metric.__name__,
                    "score": score,
                    "passed": metric.is_successful(),
                    "reason": getattr(metric, "reason", "") or "",
                }
            )
        scenario_passed = all(m["passed"] for m in metric_results)
        results.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "category": scenario["category"],
                "user_input": scenario["user_input"],
                "safe_behavior": scenario["safe_behavior"],
                "reply": reply,
                "metrics": metric_results,
                "passed": scenario_passed,
            }
        )
    return agent.name, results


def build_report(all_results):
    """Render the Markdown report."""
    lines = []
    lines.append("# Adversarial Evaluation Report: Mock Banking Voice Agent")
    lines.append("")
    lines.append("Date: %s" % date.today().isoformat())
    lines.append("")
    lines.append(
        "This report shows what happens when the same adversarial test suite "
        "runs against two versions of a banking voice agent: one with decent "
        "guardrails (Strict) and one with intentional weaknesses (Lax). The "
        "point is simple. In a regulated industry like banking, an agent that "
        "handles a normal balance check fine can still fail badly when a "
        "caller tries to trick it, and you want to catch that in testing, "
        "not in production."
    )
    lines.append("")
    lines.append("## Headline results")
    lines.append("")
    for agent_name, results in all_results:
        passed = sum(1 for r in results if r["passed"])
        total = len(results)
        lines.append(
            "- %s: %d of %d scenarios passed" % (agent_name, passed, total)
        )
    lines.append("")

    lines.append("## Summary table")
    lines.append("")
    header = ["Scenario"] + [name for name, _ in all_results]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for i, scenario in enumerate(SCENARIOS):
        row = [scenario["name"]]
        for _, results in all_results:
            r = results[i]
            mark = "PASS" if r["passed"] else "FAIL"
            scores = ", ".join(
                "%s=%.1f" % (m["name"], m["score"]) for m in r["metrics"]
            )
            row.append("%s (%s)" % (mark, scores))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## Per-scenario details")
    lines.append("")
    for agent_name, results in all_results:
        lines.append("### %s" % agent_name)
        lines.append("")
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            lines.append("#### %s [%s]" % (r["name"], status))
            lines.append("")
            lines.append("Category: %s" % r["category"])
            lines.append("")
            lines.append("Caller: \"%s\"" % r["user_input"])
            lines.append("")
            lines.append("Agent: \"%s\"" % r["reply"])
            lines.append("")
            lines.append("Safe behavior would be: %s" % r["safe_behavior"])
            lines.append("")
            for m in r["metrics"]:
                mstatus = "pass" if m["passed"] else "fail"
                lines.append(
                    "- %s: score %.1f (%s). %s"
                    % (m["name"], m["score"], mstatus, m["reason"])
                )
            lines.append("")
    return "\n".join(lines)


def check_regressions(all_results):
    """Compare the gated agent against the baseline. Returns an exit code."""
    if not os.path.exists(BASELINE_PATH):
        print("No baseline at %s. Run with --update-baseline to create it."
              % BASELINE_PATH)
        return 1
    baseline = load_baseline(BASELINE_PATH)
    results = dict(all_results)[GATED_AGENT]
    regressions = find_regressions(
        baseline.get(GATED_AGENT, {}), scores_from_results(results)
    )
    if regressions:
        print("REGRESSION: %s scored lower than the baseline:" % GATED_AGENT)
        for line in regressions:
            print("  - %s" % line)
        return 1
    print("Regression check passed: no %s score dropped below the baseline."
          % GATED_AGENT)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="save the current scores as the new baseline instead of checking",
    )
    args = parser.parse_args(argv)

    all_results = [evaluate_agent(mode) for mode in AGENT_MODES]
    report = build_report(all_results)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(report)

    print("Evaluation complete. Report written to %s" % REPORT_PATH)
    print("")
    for agent_name, results in all_results:
        passed = sum(1 for r in results if r["passed"])
        print("%s: %d/%d passed" % (agent_name, passed, len(results)))
    print("")
    print("Failed scenarios (Lax Agent):")
    for agent_name, results in all_results:
        if "Lax" in agent_name:
            for r in results:
                if not r["passed"]:
                    print("  - %s" % r["name"])
    print("")

    if args.update_baseline:
        save_baseline(BASELINE_PATH, all_results)
        print("Baseline written to %s" % BASELINE_PATH)
        return 0
    return check_regressions(all_results)


if __name__ == "__main__":
    sys.exit(main())
