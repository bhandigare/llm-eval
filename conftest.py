# conftest.py — shared fixtures + HTML report summary hook
import pytest, json
from src.bot import answer
from src.reporter import WRITTEN_REPORTS


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def golden_dataset():
    with open("data/golden_dataset.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def bot_outputs(golden_dataset):
    # Generate all outputs once per session — avoids repeated API calls
    return [
        {**case, "output": answer(case["question"], case.get("context", ""))}
        for case in golden_dataset
    ]


# ── Terminal-summary hook: show HTML report paths after every pytest run ──────
#
# Pytest's pytest_terminal_summary hook runs AFTER all tests finish and AFTER
# the standard summary (PASSED/FAILED counts), regardless of -s, -q, or -v
# flags. This is the official, robust way to surface report paths so the user
# always sees them — including on test failures.

# ANSI escape codes for terminal styling
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_BLUE   = "\033[34m"
_GREY   = "\033[90m"


def _level_colour(level: str) -> str:
    return {
        "HIGH":    _GREEN,
        "MEDIUM":  _YELLOW,
        "LOW":     _RED,
        "NOT RUN": _GREY,
    }.get(level, "")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a clickable list of every HTML report generated this run."""
    if not WRITTEN_REPORTS:
        return

    tr = terminalreporter
    tr.write_sep("=", "HTML Reports Generated", bold=True, blue=True)

    # Column widths
    name_w  = max(len(r["layer_id"]) for r in WRITTEN_REPORTS) + 2
    score_w = 12

    # Header
    tr.write_line(
        f"  {'Layer':<{name_w}}{'Result':<14}{'Score':<{score_w}}Path"
    )
    tr.write_line(f"  {'-' * (name_w + 14 + score_w + 60)}")

    for rpt in WRITTEN_REPORTS:
        col      = _level_colour(rpt["level"])
        level    = f"{col}{_BOLD}{rpt['level']:<8}{_RESET}"
        score    = f"{rpt['passed']}/{rpt['total']}"
        pct      = f"({rpt['pass_rate'] * 100:.0f}%)"
        # file:// URLs are rendered as clickable in most modern terminals
        # (iTerm2, VS Code, Warp, Windows Terminal, recent GNOME Terminal)
        link     = f"{_BLUE}{rpt['file_url']}{_RESET}"

        tr.write_line(
            f"  {rpt['layer_id']:<{name_w}}"
            f"{level}      "
            f"{score:>6} {_DIM}{pct}{_RESET}   "
            f"{link}"
        )

    tr.write_line("")
    tr.write_line(
        f"  {_DIM}Open any report in your browser, or cmd/ctrl-click the "
        f"file:// links above.{_RESET}"
    )
    tr.write_line(
        f"  {_DIM}All reports live in: ./reports/{_RESET}"
    )
    tr.write_sep("=", "end of report list", blue=True)


# ── Reset the report registry at the start of each session ────────────────────

def pytest_sessionstart(session):
    """Clear stale report entries from a previous in-process invocation."""
    WRITTEN_REPORTS.clear()
