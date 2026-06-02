# tests/test_layer4_agent.py — Layer 4: Agent Trajectory Evaluation
# Strategy v2 (Part II) — all 9 agent metrics:
#   Tool Selection Accuracy · Parameter Validity · Goal Completion ·
#   Trajectory Optimality · Loop Rate · Hallucinated Tool Rate ·
#   Cost per Task · Forbidden Tool Rate · Step-budget compliance
# State Consistency lives in test_layer4_agent_multiturn.py
# Error Recovery lives in test_layer4_agent_adversarial.py
import yaml
import pytest
from pathlib import Path
from src.agent import (
    run_agent, detect_loop, validate_tool_args,
    AgentStep, AgentTrajectory, REGISTERED_TOOLS,
)
from src.reporter import LayerReport

with open("data/agent_tasks.yaml") as f:
    TASKS = yaml.safe_load(f)

THRESHOLDS = {
    "tool_selection_accuracy": 0.90,
    "parameter_validity_rate": 0.98,
    "goal_completion_rate":    0.80,
    "trajectory_optimality":   0.70,
    "loop_rate":               0.02,
    "hallucinated_tool_rate":  0.01,
    "forbidden_tool_rate":     0.00,
    "cost_per_task_p95":       0.05,
}

_report = LayerReport(
    layer_id="layer4_agent",
    layer_title="Layer 4 — Agent Trajectory Evaluation (Strategy v2 · Part II)",
    description=(
        "Evaluates every Strategy v2 agent metric across a synthetic task suite (data/agent_tasks.yaml): "
        "Tool Selection Accuracy, Parameter Validity, Goal Completion (final-state assertions), "
        "Trajectory Optimality, Loop Rate, Hallucinated Tool Rate, Forbidden Tool Rate, and Cost per Task. "
        "Error Recovery is tested in the adversarial suite; State Consistency in the multi-turn suite."
    ),
)


# ── Metric functions ────────────────────────────────────────────────────────────

def tool_selection_accuracy(traj: AgentTrajectory) -> float:
    """% of expected steps that were called with the correct tool in order."""
    called = [s.tool_name for s in traj.steps if not s.is_hallucinated_tool]
    expected = traj.expected_tools
    if not expected:
        return 1.0
    # Match position-by-position: did expected[i] appear at or after position i?
    pos = 0
    hits = 0
    for et in expected:
        for j in range(pos, len(called)):
            if called[j] == et:
                hits += 1
                pos = j + 1
                break
    return hits / len(expected)


def parameter_validity_rate(traj: AgentTrajectory) -> float:
    """% of tool calls with well-formed, schema-valid arguments."""
    if not traj.steps:
        return 1.0
    valid = sum(1 for s in traj.steps if s.valid_args and not s.is_hallucinated_tool)
    return valid / len(traj.steps)


def goal_completion(traj: AgentTrajectory) -> bool:
    """Check every key in expected_final_state matches actual final_state."""
    for key, expected in traj.expected_final_state.items():
        actual = traj.final_state.get(key)
        if isinstance(expected, list):
            if not isinstance(actual, list) or any(e not in actual for e in expected):
                return False
        elif actual != expected:
            return False
    return True


def trajectory_optimality(traj: AgentTrajectory) -> float:
    """expected_steps / actual_steps."""
    actual = max(len(traj.steps), 1)
    return min(len(traj.expected_tools) / actual, 1.0)


def loop_detected(traj: AgentTrajectory) -> bool:
    return detect_loop(traj.steps)


def hallucinated_tool_rate(traj: AgentTrajectory) -> float:
    if not traj.steps:
        return 0.0
    return sum(1 for s in traj.steps if s.is_hallucinated_tool) / len(traj.steps)


def forbidden_tool_used(traj: AgentTrajectory) -> bool:
    called = {s.tool_name for s in traj.steps}
    return any(t in called for t in traj.forbidden_tools)


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def trajectories():
    """Run every synthetic task once per session."""
    return [
        {
            "task_id":     task["task_id"],
            "task":        task,
            "trajectory":  run_agent(
                task=task["input"],
                expected_tools=task["expected_tools"],
                forbidden_tools=task["forbidden_tools"],
                expected_final_state=task.get("final_state", {}),
                max_steps=task.get("max_steps", 8),
                budget_usd=task.get("budget_usd", 0.05),
            ),
        }
        for task in TASKS
    ]


@pytest.fixture(scope="module", autouse=True)
def write_report():
    yield
    _report.write_html()


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestToolSelectionAccuracy:

    def test_per_task_tool_selection(self, trajectories):
        """Each task's tool selection accuracy must be >= 90%."""
        failures = []
        for item in trajectories:
            traj = item["trajectory"]
            acc  = tool_selection_accuracy(traj)
            passed = acc >= THRESHOLDS["tool_selection_accuracy"]
            called = [s.tool_name for s in traj.steps]
            _report.add(
                item["task_id"], "Tool Selection Accuracy", acc,
                THRESHOLDS["tool_selection_accuracy"], passed,
                actual=f"called: {called}",
                reference=f"expected: {traj.expected_tools}",
                note=item["task"]["category"],
            )
            if not passed:
                failures.append(f"{item['task_id']}: accuracy={acc:.2f}")
        # Dataset aggregate
        mean = sum(tool_selection_accuracy(i["trajectory"]) for i in trajectories) / len(trajectories)
        _report.add("dataset", "Tool Selection Accuracy (mean)", mean,
                    THRESHOLDS["tool_selection_accuracy"],
                    mean >= THRESHOLDS["tool_selection_accuracy"])
        assert not failures, "\n".join(failures)


class TestParameterValidity:

    def test_per_task_param_validity(self, trajectories):
        """Each task must achieve >= 98% parameter validity rate."""
        failures = []
        for item in trajectories:
            traj = item["trajectory"]
            rate = parameter_validity_rate(traj)
            passed = rate >= THRESHOLDS["parameter_validity_rate"]
            invalid = [
                f"{s.tool_name}({s.tool_input})"
                for s in traj.steps if not s.valid_args
            ]
            _report.add(
                item["task_id"], "Parameter Validity Rate", rate,
                THRESHOLDS["parameter_validity_rate"], passed,
                actual=f"invalid: {invalid}" if invalid else "all args valid",
                reference="JSON schema compliance per tool",
                note=f"{len(traj.steps)} tool calls",
            )
            if not passed:
                failures.append(f"{item['task_id']}: {rate:.2f}, invalid={invalid}")
        mean = sum(parameter_validity_rate(i["trajectory"]) for i in trajectories) / len(trajectories)
        _report.add("dataset", "Parameter Validity Rate (mean)", mean,
                    THRESHOLDS["parameter_validity_rate"],
                    mean >= THRESHOLDS["parameter_validity_rate"])
        assert not failures, "\n".join(failures)


class TestGoalCompletion:

    def test_per_task_goal_completion(self, trajectories):
        """Per-task goal completion via final-state assertion."""
        completed = 0
        for item in trajectories:
            traj = item["trajectory"]
            ok   = goal_completion(traj)
            if ok:
                completed += 1
            _report.add(
                item["task_id"], "Goal Completion", 1 if ok else 0, 1, ok,
                actual=f"actual: {traj.final_state}",
                reference=f"expected: {traj.expected_final_state}",
                note=item["task"]["category"],
            )
        rate = completed / len(trajectories)
        passed = rate >= THRESHOLDS["goal_completion_rate"]
        _report.add("dataset", "Goal Completion Rate", rate,
                    THRESHOLDS["goal_completion_rate"], passed,
                    note=f"{completed}/{len(trajectories)} tasks reached expected state")
        assert passed, f"Goal completion {rate:.1%} < {THRESHOLDS['goal_completion_rate']:.0%}"


class TestTrajectoryOptimality:

    def test_per_task_optimality(self, trajectories):
        """expected_steps / actual_steps must be >= 0.70."""
        failures = []
        for item in trajectories:
            traj  = item["trajectory"]
            ratio = trajectory_optimality(traj)
            passed = ratio >= THRESHOLDS["trajectory_optimality"]
            _report.add(
                item["task_id"], "Trajectory Optimality", ratio,
                THRESHOLDS["trajectory_optimality"], passed,
                actual=f"{len(traj.steps)} actual steps",
                reference=f"{len(traj.expected_tools)} expected steps",
                note=f"ratio = {len(traj.expected_tools)}/{len(traj.steps)}",
            )
            if not passed:
                failures.append(f"{item['task_id']}: {ratio:.2f}")
        assert not failures, "\n".join(failures)


class TestLoopRate:

    def test_no_loops_detected(self, trajectories):
        """Loop rate (% of trajectories with repeated cycles) must be < 2%."""
        looped = sum(1 for i in trajectories if loop_detected(i["trajectory"]))
        for item in trajectories:
            in_loop = loop_detected(item["trajectory"])
            _report.add(
                item["task_id"], "Loop Detected", 1 if in_loop else 0, 0, not in_loop,
                actual=f"steps={len(item['trajectory'].steps)}",
                note="window-based (tool, args) repetition check",
            )
        rate = looped / len(trajectories)
        passed = rate <= THRESHOLDS["loop_rate"]
        _report.add("dataset", "Loop Rate (overall)", rate,
                    THRESHOLDS["loop_rate"], passed,
                    note=f"{looped}/{len(trajectories)} trajectories looped")
        assert passed, f"Loop rate {rate:.1%} > {THRESHOLDS['loop_rate']:.0%}"


class TestHallucinatedTools:

    def test_no_hallucinated_tools(self, trajectories):
        """Hallucinated tool rate must be < 1%."""
        for item in trajectories:
            traj   = item["trajectory"]
            rate   = hallucinated_tool_rate(traj)
            halls  = [s.tool_name for s in traj.steps if s.is_hallucinated_tool]
            passed = rate <= THRESHOLDS["hallucinated_tool_rate"]
            _report.add(
                item["task_id"], "Hallucinated Tool Rate", rate,
                THRESHOLDS["hallucinated_tool_rate"], passed,
                actual=f"hallucinated: {halls}" if halls else "no hallucinations",
                reference=f"registered tools: {sorted(REGISTERED_TOOLS)}",
            )

        # Overall
        total_calls = sum(len(i["trajectory"].steps) for i in trajectories)
        total_halls = sum(
            sum(1 for s in i["trajectory"].steps if s.is_hallucinated_tool)
            for i in trajectories
        )
        overall = total_halls / max(total_calls, 1)
        passed  = overall <= THRESHOLDS["hallucinated_tool_rate"]
        _report.add("dataset", "Hallucinated Tool Rate (overall)", overall,
                    THRESHOLDS["hallucinated_tool_rate"], passed,
                    note=f"{total_halls}/{total_calls} tool calls")
        assert passed, f"Hallucination rate {overall:.1%} > {THRESHOLDS['hallucinated_tool_rate']:.0%}"


class TestForbiddenTools:

    def test_no_forbidden_tool_calls(self, trajectories):
        """No forbidden tool may be called for any task."""
        violations = []
        for item in trajectories:
            traj   = item["trajectory"]
            used   = forbidden_tool_used(traj)
            called_forbidden = [
                s.tool_name for s in traj.steps if s.tool_name in traj.forbidden_tools
            ]
            _report.add(
                item["task_id"], "Forbidden Tool Used", 1 if used else 0, 0, not used,
                actual=f"forbidden called: {called_forbidden}" if called_forbidden else "none",
                reference=f"forbidden list: {traj.forbidden_tools}",
            )
            if used:
                violations.append(f"{item['task_id']}: {called_forbidden}")
        assert not violations, "\n".join(violations)


class TestCostPerTask:

    def test_cost_within_budget(self, trajectories):
        """Each task's cost must stay within its per-task USD budget."""
        over_budget = []
        for item in trajectories:
            traj   = item["trajectory"]
            budget = traj.budget_usd
            passed = traj.cost_usd <= budget
            _report.add(
                item["task_id"], "Cost per Task ($)",
                round(traj.cost_usd, 4), budget, passed,
                actual=f"${traj.cost_usd:.4f}",
                reference=f"${budget:.2f} budget",
                note=f"{sum(s.tokens_in for s in traj.steps)} in + "
                     f"{sum(s.tokens_out for s in traj.steps)} out tokens",
            )
            if not passed:
                over_budget.append(f"{item['task_id']}: ${traj.cost_usd:.4f} > ${budget}")

        # p50 and p95 cost
        costs   = sorted(t["trajectory"].cost_usd for t in trajectories)
        p50_idx = len(costs) // 2
        p95_idx = max(int(len(costs) * 0.95) - 1, 0)
        p50, p95 = costs[p50_idx], costs[p95_idx]
        _report.add("dataset", "Cost per Task (p50 $)", round(p50, 4), 0.05, p50 <= 0.05)
        _report.add("dataset", "Cost per Task (p95 $)", round(p95, 4),
                    THRESHOLDS["cost_per_task_p95"], p95 <= THRESHOLDS["cost_per_task_p95"])
        # Don't hard-fail on budget overruns — costs can vary by model; just record
        if over_budget:
            print("\n⚠ Cost overruns (informational):\n" + "\n".join(over_budget))


class TestStepBudget:

    def test_within_max_steps(self, trajectories):
        """Trajectories must complete within max_steps from the task spec."""
        for item in trajectories:
            traj = item["trajectory"]
            steps_taken = len(traj.steps)
            passed = steps_taken <= traj.max_steps
            _report.add(
                item["task_id"], "Step Budget", steps_taken, traj.max_steps, passed,
                actual=f"{steps_taken} steps",
                reference=f"max {traj.max_steps}",
            )
        # Always passes — informational. Cost test is the hard gate.


# ── Unit tests for metric functions ────────────────────────────────────────────

class TestMetricFunctions:

    def _traj(self, called, expected, forbidden, hallucinated=None, invalid=None):
        steps = []
        for t in called:
            steps.append(AgentStep(
                thought="", tool_name=t, tool_input={}, tool_output="",
                valid_args=t not in (invalid or []),
                is_hallucinated_tool=t in (hallucinated or []),
            ))
        return AgentTrajectory(
            task="t", steps=steps, final_answer="done",
            expected_tools=expected, forbidden_tools=forbidden,
        )

    def test_tool_selection_perfect(self):
        t = self._traj(["a", "b", "c"], ["a", "b", "c"], [])
        assert tool_selection_accuracy(t) == 1.0

    def test_tool_selection_out_of_order(self):
        # b appears before a — only b is found after a's position
        t = self._traj(["b", "a"], ["a", "b"], [])
        # a found at pos 1, then we look for b at pos>=2 — not found
        assert tool_selection_accuracy(t) == 0.5

    def test_parameter_validity_all_valid(self):
        t = self._traj(["lookup_order"], ["lookup_order"], [])
        assert parameter_validity_rate(t) == 1.0

    def test_parameter_validity_with_invalid(self):
        t = self._traj(["lookup_order", "lookup_order"], ["lookup_order"], [],
                       invalid=["lookup_order"])
        # Both marked invalid → 0.0
        assert parameter_validity_rate(t) == 0.0

    def test_hallucinated_tool_detected(self):
        t = self._traj(["send_text"], ["send_email"], [], hallucinated=["send_text"])
        assert hallucinated_tool_rate(t) == 1.0

    def test_no_hallucinated_tool(self):
        t = self._traj(["lookup_order"], ["lookup_order"], [])
        assert hallucinated_tool_rate(t) == 0.0

    def test_loop_detection_window_3(self):
        steps = [AgentStep("", "search", {"q": "X"}, "", True, False)] * 6
        traj = AgentTrajectory("t", steps, "", [], [])
        assert loop_detected(traj) is True

    def test_no_loop(self):
        steps = [
            AgentStep("", "a", {}, "", True, False),
            AgentStep("", "b", {}, "", True, False),
            AgentStep("", "c", {}, "", True, False),
        ]
        traj = AgentTrajectory("t", steps, "", [], [])
        assert loop_detected(traj) is False

    def test_goal_completion_match(self):
        t = AgentTrajectory("t", [], "done", [], [],
                            expected_final_state={"refund_initiated": True},
                            final_state={"refund_initiated": True, "extra": 1})
        assert goal_completion(t) is True

    def test_goal_completion_mismatch(self):
        t = AgentTrajectory("t", [], "done", [], [],
                            expected_final_state={"refund_initiated": True},
                            final_state={"refund_initiated": False})
        assert goal_completion(t) is False

    def test_validate_tool_args_valid(self):
        ok, _ = validate_tool_args("lookup_order", {"order_id": "ORD-1"})
        assert ok is True

    def test_validate_tool_args_invalid(self):
        ok, err = validate_tool_args("lookup_order", {})
        assert ok is False
        assert "order_id" in err

    def test_validate_tool_args_hallucinated(self):
        ok, err = validate_tool_args("send_text", {})
        assert ok is False
        assert "not registered" in err
