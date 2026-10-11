"""Score-regression gate: the strict agent must never score lower than the
saved baseline on any (scenario, metric) pair.

Run with: python -m pytest tests/
"""

import json

import run_eval
from agent.mock_voice_agent import MockVoiceAgent
from regression.baseline import find_regressions, load_baseline, save_baseline, scores_from_results

BASELINE = {
    "family_member_claim": {"account_holder_disclosure": 1.0, "refusal": 1.0},
    "baseline_balance": {"data_leakage": 1.0},
}


# -- comparison logic ------------------------------------------------------

def test_no_regressions_when_scores_match_the_baseline():
    assert find_regressions(BASELINE, BASELINE) == []


def test_reports_a_drop_on_a_single_metric():
    current = {
        "family_member_claim": {"account_holder_disclosure": 0.0, "refusal": 1.0},
        "baseline_balance": {"data_leakage": 1.0},
    }

    regressions = find_regressions(BASELINE, current)

    assert regressions == [
        "family_member_claim / account_holder_disclosure: 1.0 -> 0.0"
    ]


def test_a_metric_missing_from_the_current_run_counts_as_a_regression():
    current = {"baseline_balance": {"data_leakage": 1.0}}

    regressions = find_regressions(BASELINE, current)

    assert regressions == [
        "family_member_claim / account_holder_disclosure: 1.0 -> missing",
        "family_member_claim / refusal: 1.0 -> missing",
    ]


def test_new_scenarios_and_improvements_are_not_regressions():
    baseline = {"baseline_balance": {"data_leakage": 0.0}}
    current = {
        "baseline_balance": {"data_leakage": 1.0},
        "brand_new_scenario": {"refusal": 0.0},
    }

    assert find_regressions(baseline, current) == []


# -- persistence -----------------------------------------------------------

def test_baseline_round_trips_through_disk(tmp_path):
    path = tmp_path / "baseline.json"
    all_results = [run_eval.evaluate_agent("strict")]

    save_baseline(str(path), all_results)

    assert load_baseline(str(path))["Strict Agent"] == scores_from_results(
        all_results[0][1]
    )


def test_scores_from_results_keys_by_scenario_id_and_metric_key():
    _, results = run_eval.evaluate_agent("strict")

    scores = scores_from_results(results)

    assert scores["family_member_claim"] == {
        "account_holder_disclosure": 1.0,
        "refusal": 1.0,
    }


# -- the gate in run_eval.py -----------------------------------------------

def _run_main(monkeypatch, tmp_path, *args):
    monkeypatch.setattr(run_eval, "REPORT_PATH", str(tmp_path / "report.md"))
    return run_eval.main(list(args))


def test_committed_baseline_has_no_regressions_against_the_current_strict_agent():
    baseline = load_baseline(run_eval.BASELINE_PATH)
    _, results = run_eval.evaluate_agent("strict")

    assert find_regressions(baseline["Strict Agent"], scores_from_results(results)) == []


def test_run_passes_when_strict_scores_match_the_baseline(monkeypatch, tmp_path):
    assert _run_main(monkeypatch, tmp_path) == 0


def test_run_fails_when_a_strict_score_drops(monkeypatch, tmp_path):
    # Simulate a regression: the strict agent starts trusting family claims.
    lax_reply = MockVoiceAgent("lax")._handle_family_claim()
    monkeypatch.setattr(
        MockVoiceAgent, "_handle_family_claim", lambda self: lax_reply
    )

    assert _run_main(monkeypatch, tmp_path) == 1


def test_run_fails_when_the_baseline_file_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(run_eval, "BASELINE_PATH", str(tmp_path / "nope.json"))

    assert _run_main(monkeypatch, tmp_path) == 1


def test_update_baseline_writes_the_file_and_passes(monkeypatch, tmp_path):
    path = tmp_path / "baseline.json"
    monkeypatch.setattr(run_eval, "BASELINE_PATH", str(path))

    assert _run_main(monkeypatch, tmp_path, "--update-baseline") == 0
    assert set(json.loads(path.read_text())) == {"Strict Agent", "Lax Agent"}
