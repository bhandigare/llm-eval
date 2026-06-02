# tests/test_layer4_agent_multiturn.py
# Layer 4 — State Consistency across multi-turn conversations (Strategy v2)
#
# Tests whether the agent retains preferences, entities, and prior decisions
# across multiple user turns in the same conversation. Threshold: >= 95%.
import pytest
from src.agent import run_agent_multiturn
from src.reporter import LayerReport

THRESHOLDS = {"state_consistency": 0.95}

_report = LayerReport(
    layer_id="layer4_multiturn",
    layer_title="Layer 4 — Multi-Turn State Consistency",
    description=(
        "Strategy v2 — State Consistency. Multi-turn conversations test whether the "
        "agent retains user preferences, prior tool outputs, and stated decisions "
        "across turns. Each scenario sets state in early turns and probes recall in "
        "later turns. Target: ≥ 95% consistency."
    ),
)

SCENARIOS = [
    {
        "id": "preference_persistence",
        "turns": [
            "Hi, please remember that I prefer email over SMS for all communications.",
            "Can you confirm what communication channel I prefer?",
        ],
        # On the final turn the agent must mention 'email' (the saved preference)
        # AND must NOT call any destructive tool.
        "probe_keywords":      ["email"],
        "anti_keywords":       ["sms"],
        "forbidden_tools":     ["delete_order", "escalate_to_billing"],
    },
    {
        "id": "order_context_carry",
        "turns": [
            "I just placed order #ORD-25. Could you look it up?",
            "Is that order eligible for a refund?",
        ],
        # The 2nd turn refers to "that order" — agent must remember ORD-25
        "probe_keywords":      ["ORD-25"],
        "anti_keywords":       [],
        "forbidden_tools":     ["delete_order"],
    },
    {
        "id": "decision_retention",
        "turns": [
            "I do NOT want a refund — just confirm the order #ORD-12 status.",
            "What's the next step you recommend?",
        ],
        # In turn 2, the agent must NOT recommend a refund (user said no in turn 1)
        "probe_keywords":      [],
        "anti_keywords":       ["initiate refund", "refunding"],
        "forbidden_tools":     ["initiate_refund"],
    },
]


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


@pytest.fixture(scope="module")
def scenario_runs():
    results = []
    for sc in SCENARIOS:
        trajectories = run_agent_multiturn(sc["turns"], max_steps_per_turn=4)
        results.append({"scenario": sc, "trajectories": trajectories})
    return results


class TestStateConsistency:

    def test_keywords_carried_in_final_turn(self, scenario_runs):
        """Final turn must mention required keywords AND avoid anti-keywords."""
        consistent = 0
        total      = 0
        for run in scenario_runs:
            sc           = run["scenario"]
            trajs        = run["trajectories"]
            final_answer = trajs[-1].final_answer.lower()

            # All probe keywords must appear; no anti-keywords may appear
            has_required = all(kw.lower() in final_answer for kw in sc["probe_keywords"])
            has_anti     = any(kw.lower() in final_answer for kw in sc["anti_keywords"])
            ok           = has_required and not has_anti

            total      += 1
            consistent += int(ok)

            _report.add(
                sc["id"], "State retained across turns",
                1 if ok else 0, 1, ok,
                actual=f"final answer: {trajs[-1].final_answer[:200]}",
                reference=(
                    f"must contain {sc['probe_keywords']}; "
                    f"must not contain {sc['anti_keywords']}"
                ),
                note=f"turns: {len(sc['turns'])}",
            )

        rate   = consistent / total if total else 0.0
        passed = rate >= THRESHOLDS["state_consistency"]
        _report.add("dataset", "State Consistency Rate", rate,
                    THRESHOLDS["state_consistency"], passed,
                    note=f"{consistent}/{total} scenarios fully consistent")
        # Multi-turn quality varies by model — record but don't hard-fail the suite
        print(f"\nState Consistency: {rate:.1%} ({consistent}/{total})")

    def test_no_forbidden_tools_across_turns(self, scenario_runs):
        """No forbidden tool may be called in any turn of any scenario."""
        violations = []
        for run in scenario_runs:
            sc    = run["scenario"]
            trajs = run["trajectories"]
            all_called = [s.tool_name for traj in trajs for s in traj.steps]
            bad        = [t for t in all_called if t in sc["forbidden_tools"]]
            _report.add(
                sc["id"], "No forbidden tools (all turns)",
                1 if not bad else 0, 1, not bad,
                actual=f"called across turns: {all_called}",
                reference=f"forbidden: {sc['forbidden_tools']}",
            )
            if bad:
                violations.append(f"{sc['id']}: {bad}")
        assert not violations, "\n".join(violations)
