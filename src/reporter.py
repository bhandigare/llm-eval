# src/reporter.py — HTML report engine for all eval layers
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from jinja2 import Template

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Session-level registry of reports written this run.
# Populated by LayerReport.write_html() and read by the pytest_terminal_summary
# hook in conftest.py so the paths show up at the end of every pytest run.
WRITTEN_REPORTS: list[dict] = []


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class ScoreRow:
    case_id:   str
    metric:    str
    score:     float | str
    threshold: float | str
    passed:    bool
    actual:    str = ""
    reference: str = ""
    note:      str = ""

    @property
    def score_pct(self) -> float | None:
        """Score as 0-1 fraction of threshold for sparkbar (None if non-numeric)."""
        try:
            s = float(self.score)
            t = float(self.threshold)
            return min(s / t, 2.0) / 2.0 if t else None   # cap at 2× threshold
        except (ValueError, TypeError):
            return None

    @property
    def score_display(self) -> str:
        if isinstance(self.score, float):
            return f"{self.score:.3f}"
        return str(self.score)

    @property
    def threshold_display(self) -> str:
        if isinstance(self.threshold, float):
            return f"{self.threshold:.3f}"
        return str(self.threshold)

    @property
    def margin_pct(self) -> str:
        """
        Distance from threshold, signed by pass/fail direction.

        For 'higher is better' metrics passing → positive (above threshold).
        For 'lower is better' metrics passing → also positive (below threshold).
        The sign always tracks pass/fail, not raw score vs threshold direction.
        """
        try:
            s, t = float(self.score), float(self.threshold)
            if t == 0:
                # Threshold of 0 (e.g. forbidden_tool_rate, loop count): margin is
                # +100% if passing, -100% if failing. Score magnitude is the deviation.
                if self.passed:
                    return "+100%"
                return f"{-abs(s) * 100:+.0f}%" if abs(s) <= 1 else "-fail"
            magnitude = abs(s - t) / abs(t)
            return f"{magnitude * 100:+.0f}%" if self.passed else f"{-magnitude * 100:+.0f}%"
        except (ValueError, TypeError):
            return ""


@dataclass
class LayerReport:
    layer_id:    str
    layer_title: str
    description: str = ""
    rows:        list[ScoreRow] = field(default_factory=list)
    extra_info:  dict[str, Any] = field(default_factory=dict)

    def add(self, case_id, metric, score, threshold, passed,
            actual="", reference="", note="") -> None:
        self.rows.append(ScoreRow(
            case_id=str(case_id), metric=metric, score=score,
            threshold=threshold, passed=passed,
            actual=str(actual)[:400], reference=str(reference)[:400],
            note=str(note)[:200],
        ))

    # ── Aggregates ──────────────────────────────────────────────────────────────

    @property
    def total(self)         -> int:   return len(self.rows)
    @property
    def passed_count(self)  -> int:   return sum(1 for r in self.rows if r.passed)
    @property
    def failed_count(self)  -> int:   return self.total - self.passed_count
    @property
    def pass_rate(self)     -> float: return self.passed_count / self.total if self.total else 0.0

    def metrics_grouped(self) -> dict[str, list[ScoreRow]]:
        """Rows grouped by metric name, preserving insertion order."""
        groups: dict[str, list[ScoreRow]] = {}
        for r in self.rows:
            groups.setdefault(r.metric, []).append(r)
        return groups

    # ── Confidence analysis ─────────────────────────────────────────────────────

    @property
    def confidence(self) -> dict:
        if self.total == 0:
            return {
                "level": "NOT RUN", "colour": "#64748b", "bg": "#1e293b",
                "label": "No assertions collected yet",
                "pass_rate": 0.0, "mean_margin": 0.0,
                "passed": 0, "total": 0,
                "metric_summary": {}, "failed_metrics": [],
            }

        margins = []
        for r in self.rows:
            try:
                s, t = float(r.score), float(r.threshold)
                if t == 0:
                    # Threshold-0 metrics (loop, forbidden tools): +1 if passed, -1 if failed
                    margins.append(1.0 if r.passed else -1.0)
                    continue
                magnitude = abs(s - t) / abs(t)
                # Sign tracks pass/fail, not raw direction — works for both
                # 'higher is better' and 'lower is better' metrics.
                margins.append(magnitude if r.passed else -magnitude)
            except (ValueError, TypeError):
                pass

        mean_margin = sum(margins) / len(margins) if margins else 0.0
        pr = self.pass_rate

        if pr >= 0.90 and mean_margin >= 0.10:
            level, colour, bg = "HIGH",   "#22c55e", "#052e16"
        elif pr >= 0.70 or mean_margin >= 0.0:
            level, colour, bg = "MEDIUM", "#f59e0b", "#1c1007"
        else:
            level, colour, bg = "LOW",    "#ef4444", "#1f0707"

        metric_rates: dict[str, dict] = {}
        for r in self.rows:
            m = metric_rates.setdefault(r.metric, {"pass": 0, "total": 0, "scores": []})
            m["total"] += 1
            if r.passed:
                m["pass"] += 1
            try:
                m["scores"].append(float(r.score))
            except (ValueError, TypeError):
                pass

        metric_summary = {
            k: {
                "rate":   v["pass"] / v["total"],
                "pass":   v["pass"],
                "total":  v["total"],
                "avg":    sum(v["scores"]) / len(v["scores"]) if v["scores"] else None,
            }
            for k, v in metric_rates.items()
        }

        failed_metrics = [
            k for k, v in metric_summary.items() if v["rate"] < 1.0
        ]

        return {
            "level": level, "colour": colour, "bg": bg,
            "label": label if (label := f"{'HIGH' if level=='HIGH' else 'MEDIUM' if level=='MEDIUM' else 'LOW'} Confidence") else "",
            "pass_rate": pr, "mean_margin": mean_margin,
            "passed": self.passed_count, "total": self.total,
            "metric_summary": metric_summary,
            "failed_metrics": failed_metrics,
        }

    # ── HTML render ─────────────────────────────────────────────────────────────

    def write_html(self) -> Path:
        # Lazy import to avoid circular dep at module load
        from src.recommendations import generate_recommendations, PRIORITY_COLOUR

        conf = self.confidence
        # fix label for NOT RUN case
        if conf["level"] == "NOT RUN":
            conf["label"] = "No Assertions Collected"
        else:
            conf["label"] = f"{conf['level'].title()} Confidence"

        recommendations = generate_recommendations(self)

        path = REPORTS_DIR / f"{self.layer_id}.html"
        path.write_text(_TEMPLATE.render(
            report=self,
            conf=conf,
            groups=self.metrics_grouped(),
            recommendations=recommendations,
            priority_colour=PRIORITY_COLOUR,
            generated=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
        ), encoding="utf-8")

        # Register the report so pytest_terminal_summary can display it
        # at the end of the run, regardless of -s flag.
        WRITTEN_REPORTS.append({
            "layer_id":    self.layer_id,
            "layer_title": self.layer_title,
            "path":        path.resolve(),
            "file_url":    f"file://{path.resolve()}",
            "level":       conf["level"],
            "passed":      self.passed_count,
            "total":       self.total,
            "pass_rate":   self.pass_rate,
        })

        # Also print inline (visible only with pytest -s).
        # The terminal summary hook in conftest.py is the authoritative display.
        print(f"\n📊 Report → file://{path.resolve()}")
        return path


# ── Template ────────────────────────────────────────────────────────────────────

_TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ report.layer_title }}</title>
<style>
/* ── Reset & tokens ─────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117; --surface:#161b22; --surface2:#1c2128; --border:#30363d;
  --text:#e6edf3; --muted:#7d8590; --accent:#58a6ff;
  --pass:#3fb950; --fail:#f85149; --warn:#d29922;
  --pass-bg:#0d2118; --fail-bg:#1f0707; --warn-bg:#1c1007;
  --radius:8px; --shadow:0 1px 3px rgba(0,0,0,.4);
  font-size:14px; font-family:'Segoe UI',system-ui,-apple-system,sans-serif;
}
body{background:var(--bg);color:var(--text);padding:0;min-height:100vh}

/* ── Layout ─────────────────────────────────────── */
.page-header{background:var(--surface);border-bottom:1px solid var(--border);
  padding:1.5rem 2.5rem 1.25rem}
.page-header h1{font-size:1.35rem;font-weight:700;color:var(--text);line-height:1.3}
.breadcrumb{font-size:.78rem;color:var(--muted);margin-bottom:.4rem;
  display:flex;align-items:center;gap:.4rem}
.breadcrumb span{color:var(--muted)}
.meta-row{display:flex;align-items:center;gap:1.5rem;margin-top:.6rem;
  font-size:.8rem;color:var(--muted);flex-wrap:wrap}
.meta-row strong{color:var(--text)}
.badge{display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .6rem;
  border-radius:99px;font-size:.72rem;font-weight:600;border:1px solid}

.content{padding:2rem 2.5rem;max-width:1600px;margin:0 auto}
.section{margin-bottom:2rem}
.section-title{font-size:.7rem;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--muted);margin-bottom:.75rem;
  padding-bottom:.4rem;border-bottom:1px solid var(--border)}

/* ── Confidence panel ───────────────────────────── */
.conf-panel{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;margin-bottom:1.5rem;
}
.conf-panel-inner{
  border-left:4px solid {{ conf.colour }};
  padding:1.25rem 1.5rem;display:grid;
  grid-template-columns:140px 1fr 1fr;gap:1.25rem;align-items:start;
}
.conf-level-block{text-align:center}
.conf-level{font-size:1.5rem;font-weight:800;color:{{ conf.colour }};
  letter-spacing:.04em;line-height:1}
.conf-sublabel{font-size:.75rem;color:var(--muted);margin-top:.3rem}

.conf-stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:.5rem 1.5rem}
.conf-stat dt{font-size:.72rem;color:var(--muted);margin-bottom:.1rem}
.conf-stat dd{font-size:1.1rem;font-weight:700;color:var(--text)}
.conf-stat dd.green{color:var(--pass)}
.conf-stat dd.red{color:var(--fail)}
.conf-stat dd.warn{color:var(--warn)}

.bar-wrap{margin-top:.3rem}
.bar-label{font-size:.72rem;color:var(--muted);margin-bottom:.3rem;
  display:flex;justify-content:space-between}
.bar-outer{background:var(--surface2);border-radius:99px;height:6px;
  border:1px solid var(--border)}
.bar-inner{height:100%;border-radius:99px;
  background:linear-gradient(90deg,{{ conf.colour }},{{ conf.colour }}99)}

.metric-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.75rem}
.chip{display:inline-flex;align-items:center;gap:.35rem;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:6px;padding:.25rem .55rem;font-size:.72rem;white-space:nowrap}
.chip .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}

/* failure callout */
.fail-callout{background:var(--fail-bg);border:1px solid #6e1a1a;
  border-radius:6px;padding:.6rem 1rem;margin-top:.75rem;
  font-size:.8rem;color:#fca5a5}
.fail-callout strong{color:var(--fail)}

/* ── KPI cards ──────────────────────────────────── */
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.5rem}
.kpi-card{background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:1.1rem 1.4rem;box-shadow:var(--shadow)}
.kpi-val{font-size:2rem;font-weight:800;line-height:1;margin-bottom:.25rem}
.kpi-lbl{font-size:.75rem;color:var(--muted);font-weight:500}
.kpi-card.pass .kpi-val{color:var(--pass)}
.kpi-card.fail .kpi-val{color:var(--fail)}
.kpi-card.total .kpi-val{color:var(--accent)}
.kpi-card.rate .kpi-val{color:{{ conf.colour }}}

/* ── Metric section cards ───────────────────────── */
.metric-section{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);margin-bottom:1rem;overflow:hidden;
  box-shadow:var(--shadow);
}
.metric-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:.85rem 1.25rem;cursor:pointer;user-select:none;
  border-bottom:1px solid var(--border);
}
.metric-header:hover{background:var(--surface2)}
.metric-name{font-size:.9rem;font-weight:600;color:var(--text);
  display:flex;align-items:center;gap:.6rem}
.metric-header-right{display:flex;align-items:center;gap:.75rem;flex-shrink:0}
.pass-badge{font-size:.75rem;font-weight:600;padding:.15rem .5rem;
  border-radius:99px;white-space:nowrap}
.pass-badge.all-pass{background:var(--pass-bg);color:var(--pass);
  border:1px solid #1a4731}
.pass-badge.has-fail{background:var(--fail-bg);color:var(--fail);
  border:1px solid #6e1a1a}
.metric-avg{font-size:.78rem;color:var(--muted);font-family:'Courier New',monospace}
.chevron{color:var(--muted);font-size:.85rem;transition:transform .2s}
.metric-body{overflow:auto}

/* ── Table ──────────────────────────────────────── */
table{width:100%;border-collapse:collapse;font-size:.82rem}
thead th{
  background:var(--surface2);color:var(--muted);text-align:left;
  padding:.6rem 1rem;border-bottom:1px solid var(--border);
  white-space:nowrap;font-weight:600;font-size:.72rem;
  letter-spacing:.04em;text-transform:uppercase;position:sticky;top:0;
}
tbody tr{border-bottom:1px solid var(--border)}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:var(--surface2)}
td{padding:.6rem 1rem;vertical-align:top}
td.mono{font-family:'Courier New',monospace;font-size:.8rem}
td.case-id code{background:var(--surface2);border:1px solid var(--border);
  border-radius:4px;padding:.1rem .4rem;font-size:.75rem;color:var(--accent)}

/* score cell */
.score-wrap{display:flex;align-items:center;gap:.5rem}
.score-num{font-weight:700;font-family:'Courier New',monospace}
.score-pass{color:var(--pass)}
.score-fail{color:var(--fail)}
.score-bar{flex:1;min-width:40px;max-width:80px}
.score-bar-outer{background:var(--surface2);border-radius:99px;height:5px}
.score-bar-fill{height:5px;border-radius:99px;min-width:3px}

.margin-tag{font-size:.68rem;padding:.1rem .35rem;border-radius:4px;
  font-weight:600;white-space:nowrap}
.margin-pos{background:#052e16;color:#4ade80}
.margin-neg{background:var(--fail-bg);color:#fca5a5}

/* result pill */
.pill{display:inline-flex;align-items:center;gap:.25rem;padding:.2rem .55rem;
  border-radius:99px;font-size:.72rem;font-weight:700;letter-spacing:.02em}
.pill.pass{background:var(--pass-bg);color:var(--pass);border:1px solid #1a4731}
.pill.fail{background:var(--fail-bg);color:var(--fail);border:1px solid #6e1a1a}
.pill::before{content:'';width:5px;height:5px;border-radius:50%;
  background:currentColor;flex-shrink:0}

/* expandable text */
details{cursor:pointer}
details summary{
  color:var(--accent);font-size:.78rem;list-style:none;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  max-width:280px;display:block}
details summary::-webkit-details-marker{display:none}
details summary::before{content:'▶ ';font-size:.6rem;opacity:.7}
details[open] summary::before{content:'▼ ';font-size:.6rem;opacity:.7}
details p{
  margin-top:.4rem;color:var(--muted);font-size:.78rem;
  white-space:pre-wrap;word-break:break-word;max-width:340px;
  background:var(--surface2);border:1px solid var(--border);
  border-radius:4px;padding:.4rem .6rem;line-height:1.5}
.dash{color:var(--border);font-size:.9rem}

/* ── Footer ─────────────────────────────────────── */
.page-footer{border-top:1px solid var(--border);padding:1rem 2.5rem;
  font-size:.75rem;color:var(--muted);display:flex;
  justify-content:space-between;align-items:center;margin-top:2rem}

/* ── Recommendations panel ──────────────────────── */
.recs-section{margin-bottom:1.5rem}
.recs-banner{
  background:linear-gradient(90deg,#1f0707 0%,var(--surface) 100%);
  border:1px solid #6e1a1a;border-radius:var(--radius);
  padding:.75rem 1.25rem;margin-bottom:.75rem;
  display:flex;align-items:center;gap:.75rem;font-size:.85rem
}
.recs-banner-icon{font-size:1.2rem}
.recs-banner-text{color:var(--text)}
.recs-banner-text strong{color:#fca5a5}

.rec-card{
  background:var(--surface);border:1px solid var(--border);
  border-left:4px solid var(--warn);
  border-radius:var(--radius);padding:1rem 1.25rem 1.1rem;
  margin-bottom:.75rem;box-shadow:var(--shadow);
}
.rec-card.prio-HIGH   { border-left-color:#ef4444 }
.rec-card.prio-MEDIUM { border-left-color:#f59e0b }
.rec-card.prio-LOW    { border-left-color:#3b82f6 }

.rec-head{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin-bottom:.5rem}
.rec-prio{
  display:inline-flex;align-items:center;gap:.25rem;
  padding:.15rem .55rem;border-radius:99px;font-size:.68rem;
  font-weight:700;letter-spacing:.04em;
}
.rec-prio.prio-HIGH   { background:#3b0a0a;color:#fca5a5;border:1px solid #6e1a1a }
.rec-prio.prio-MEDIUM { background:#3b260a;color:#fcd34d;border:1px solid #785518 }
.rec-prio.prio-LOW    { background:#0a1f3b;color:#93c5fd;border:1px solid #1e3a8a }
.rec-category{
  font-size:.72rem;color:var(--muted);text-transform:uppercase;
  letter-spacing:.04em;font-weight:600;
}
.rec-title{
  font-size:.95rem;font-weight:600;color:var(--text);
  flex:1 1 100%;margin-top:.15rem;line-height:1.35
}
.rec-detail{
  font-size:.82rem;color:var(--muted);line-height:1.55;
  margin-bottom:.7rem;
}
.rec-action{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:6px;padding:.7rem .85rem;font-size:.82rem;line-height:1.6;
  color:var(--text);
}
.rec-action-label{
  font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
  color:var(--accent);font-weight:700;display:block;margin-bottom:.3rem;
}
.rec-meta{display:flex;flex-wrap:wrap;gap:1.25rem;margin-top:.6rem;
  font-size:.75rem;color:var(--muted)}
.rec-meta code{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:4px;padding:.1rem .4rem;color:var(--accent);
  font-family:'Courier New',monospace;font-size:.72rem;
}
.rec-cases{display:inline-flex;flex-wrap:wrap;gap:.25rem}
.rec-cases code{font-size:.7rem;color:var(--warn)}

/* ── Print ──────────────────────────────────────── */
@media print{
  body{background:#fff;color:#000}
  .page-header,.kpi-card,.metric-section{
    background:#fff;border-color:#ddd;box-shadow:none}
  .conf-panel-inner{border-left-width:3px}
  thead th{background:#f5f5f5;color:#333}
  .score-bar,.bar-outer,.bar-inner{display:none}
}
</style>
</head>
<body>

<!-- ── Header ── -->
<header class="page-header">
  <div class="breadcrumb">
    <span>llm-eval</span> <span>›</span>
    <span>reports</span> <span>›</span>
    <span style="color:var(--accent)">{{ report.layer_id }}</span>
  </div>
  <h1>{{ report.layer_title }}</h1>
  <div class="meta-row">
    <span>🕐 Generated <strong>{{ generated }}</strong></span>
    <span>📋 <strong>{{ conf.total }}</strong> assertions</span>
    <span>✅ <strong>{{ conf.passed }}</strong> passed</span>
    {% if conf.failed_metrics %}
    <span class="badge" style="color:var(--fail);border-color:#6e1a1a;background:var(--fail-bg)">
      ⚠ {{ conf.failed_metrics | length }} metric{{ 's' if conf.failed_metrics|length > 1 else '' }} failing
    </span>
    {% else %}
    <span class="badge" style="color:var(--pass);border-color:#1a4731;background:var(--pass-bg)">
      ✓ All metrics passing
    </span>
    {% endif %}
  </div>
  {% if report.description %}
  <div style="margin-top:.6rem;font-size:.82rem;color:var(--muted);max-width:900px;line-height:1.6">
    {{ report.description }}
  </div>
  {% endif %}
</header>

<div class="content">

<!-- ── Confidence panel ── -->
<div class="section">
  <div class="section-title">Confidence Analysis</div>
  <div class="conf-panel">
    <div class="conf-panel-inner" style="border-left-color:{{ conf.colour }}">

      <div class="conf-level-block">
        <div class="conf-level">{{ conf.level }}</div>
        <div class="conf-sublabel">{{ conf.label }}</div>
      </div>

      <div>
        <dl class="conf-stat-grid">
          <div class="conf-stat">
            <dt>Pass Rate</dt>
            <dd class="{{ 'green' if conf.pass_rate >= 0.9 else ('warn' if conf.pass_rate >= 0.7 else 'red') }}">
              {{ "%.1f"|format(conf.pass_rate * 100) }}%
            </dd>
          </div>
          <div class="conf-stat">
            <dt>Mean Score Margin</dt>
            <dd class="{{ 'green' if conf.mean_margin >= 0.1 else ('warn' if conf.mean_margin >= 0 else 'red') }}">
              {{ "%+.1f"|format(conf.mean_margin * 100) }}%
            </dd>
          </div>
          <div class="conf-stat">
            <dt>Assertions Passed</dt>
            <dd>{{ conf.passed }} / {{ conf.total }}</dd>
          </div>
          <div class="conf-stat">
            <dt>Metrics Tracked</dt>
            <dd>{{ conf.metric_summary | length }}</dd>
          </div>
        </dl>
        <div class="bar-wrap">
          <div class="bar-label">
            <span>Overall pass rate</span>
            <span>{{ "%.0f"|format(conf.pass_rate * 100) }}%</span>
          </div>
          <div class="bar-outer">
            <div class="bar-inner" style="width:{{ (conf.pass_rate * 100)|round|int }}%"></div>
          </div>
        </div>
      </div>

      <div>
        <div style="font-size:.72rem;color:var(--muted);margin-bottom:.5rem;
          text-transform:uppercase;letter-spacing:.06em;font-weight:700">
          Per-Metric Breakdown
        </div>
        <div class="metric-chips">
          {% for metric, ms in conf.metric_summary.items() %}
          {% set col = "#3fb950" if ms.rate >= 1.0 else ("#d29922" if ms.rate >= 0.7 else "#f85149") %}
          <div class="chip">
            <span class="dot" style="background:{{ col }}"></span>
            <span style="color:var(--text)">{{ metric }}</span>
            <span style="color:{{ col }};font-weight:700">{{ ms.pass }}/{{ ms.total }}</span>
            {% if ms.avg is not none %}
            <span style="color:var(--muted);font-size:.68rem">(avg {{ "%.2f"|format(ms.avg) }})</span>
            {% endif %}
          </div>
          {% endfor %}
        </div>
        {% if conf.failed_metrics %}
        <div class="fail-callout">
          <strong>⚠ Failing:</strong>
          {{ conf.failed_metrics | join(', ') }}
        </div>
        {% endif %}
      </div>

    </div>
  </div>
</div>

<!-- ── Recommendations panel (only when there are failures) ── -->
{% if recommendations %}
<div class="section recs-section">
  <div class="section-title">Recommendations — Suggested Fixes</div>

  <div class="recs-banner">
    <span class="recs-banner-icon">⚙</span>
    <span class="recs-banner-text">
      <strong>{{ recommendations | length }} actionable recommendation{% if recommendations|length > 1 %}s{% endif %}</strong>
      generated from {{ report.failed_count }} failing assertion{% if report.failed_count > 1 %}s{% endif %}.
      Ordered by priority — apply HIGH-priority items first.
    </span>
  </div>

  {% for rec in recommendations %}
  <div class="rec-card prio-{{ rec.priority }}">
    <div class="rec-head">
      <span class="rec-prio prio-{{ rec.priority }}">● {{ rec.priority }}</span>
      <span class="rec-category">{{ rec.category }}</span>
      <div class="rec-title">{{ rec.title }}</div>
    </div>

    <div class="rec-detail">{{ rec.detail }}</div>

    <div class="rec-action">
      <span class="rec-action-label">↳ Suggested action</span>
      {{ rec.suggested_action }}
    </div>

    <div class="rec-meta">
      {% if rec.file_pointer %}
      <span>📁 Edit: <code>{{ rec.file_pointer }}</code></span>
      {% endif %}
      {% if rec.affected_cases %}
      <span class="rec-cases">
        🎯 Affects:
        {% for c in rec.affected_cases %}<code>{{ c }}</code>{% endfor %}
      </span>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

<!-- ── KPI row ── -->
<div class="kpi-row">
  <div class="kpi-card pass">
    <div class="kpi-val">{{ conf.passed }}</div>
    <div class="kpi-lbl">Assertions Passed</div>
  </div>
  <div class="kpi-card fail">
    <div class="kpi-val">{{ report.failed_count }}</div>
    <div class="kpi-lbl">Assertions Failed</div>
  </div>
  <div class="kpi-card total">
    <div class="kpi-val">{{ conf.total }}</div>
    <div class="kpi-lbl">Total Assertions</div>
  </div>
  <div class="kpi-card rate">
    <div class="kpi-val">{{ "%.1f"|format(conf.pass_rate * 100) }}%</div>
    <div class="kpi-lbl">Pass Rate</div>
  </div>
</div>

<!-- ── Metric sections ── -->
<div class="section">
  <div class="section-title">Detailed Results by Metric</div>
  {% for metric, rows in groups.items() %}
  {% set m_pass = rows | selectattr('passed') | list | length %}
  {% set m_total = rows | length %}
  {% set all_ok = m_pass == m_total %}
  {% set scores = rows | map(attribute='score') | list %}
  <div class="metric-section">
    <div class="metric-header" onclick="toggle(this)">
      <div class="metric-name">
        <span>{{ metric }}</span>
      </div>
      <div class="metric-header-right">
        <span class="metric-avg" style="color:var(--muted)">{{ m_pass }}/{{ m_total }} cases</span>
        <span class="pass-badge {{ 'all-pass' if all_ok else 'has-fail' }}">
          {{ '✓ All pass' if all_ok else ('✗ ' ~ (m_total - m_pass) ~ ' failing') }}
        </span>
        <span class="chevron">▼</span>
      </div>
    </div>
    <div class="metric-body">
      <table>
        <thead>
          <tr>
            <th style="width:110px">Case ID</th>
            <th>Score</th>
            <th style="width:90px">Threshold</th>
            <th style="width:75px">Margin</th>
            <th style="width:80px">Result</th>
            <th>Actual Output</th>
            <th>Reference</th>
            <th style="width:180px">Note</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td class="case-id"><code>{{ row.case_id }}</code></td>
            <td>
              <div class="score-wrap">
                <span class="score-num {{ 'score-pass' if row.passed else 'score-fail' }}">
                  {{ row.score_display }}
                </span>
                {% if row.score_pct is not none %}
                <div class="score-bar">
                  <div class="score-bar-outer">
                    <div class="score-bar-fill"
                      style="width:{{ (row.score_pct * 100)|round|int }}%;
                             background:{{ '#3fb950' if row.passed else '#f85149' }}">
                    </div>
                  </div>
                </div>
                {% endif %}
              </div>
            </td>
            <td class="mono" style="color:var(--muted)">{{ row.threshold_display }}</td>
            <td>
              {% if row.margin_pct %}
              <span class="margin-tag {{ 'margin-pos' if row.passed else 'margin-neg' }}">
                {{ row.margin_pct }}
              </span>
              {% else %}
              <span class="dash">—</span>
              {% endif %}
            </td>
            <td>
              <span class="pill {{ 'pass' if row.passed else 'fail' }}">
                {{ 'PASS' if row.passed else 'FAIL' }}
              </span>
            </td>
            <td>
              {% if row.actual %}
              <details>
                <summary>{{ row.actual[:70] }}{% if row.actual|length > 70 %}…{% endif %}</summary>
                <p>{{ row.actual }}</p>
              </details>
              {% else %}<span class="dash">—</span>{% endif %}
            </td>
            <td>
              {% if row.reference %}
              <details>
                <summary>{{ row.reference[:70] }}{% if row.reference|length > 70 %}…{% endif %}</summary>
                <p>{{ row.reference }}</p>
              </details>
              {% else %}<span class="dash">—</span>{% endif %}
            </td>
            <td style="color:var(--muted);font-size:.75rem;line-height:1.4">
              {{ row.note }}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endfor %}
</div>

{% if report.extra_info %}
<div class="section">
  <div class="section-title">Additional Data</div>
  <div class="metric-section">
    <div style="padding:1rem 1.25rem">
      <pre style="font-size:.78rem;color:var(--muted);white-space:pre-wrap;
        word-break:break-word;line-height:1.6">{{ report.extra_info | tojson(indent=2) }}</pre>
    </div>
  </div>
</div>
{% endif %}

</div><!-- /content -->

<footer class="page-footer">
  <span>llm-eval · {{ report.layer_id }}</span>
  <span>{{ generated }}</span>
</footer>

<script>
function toggle(header) {
  const body = header.nextElementSibling;
  const chev = header.querySelector('.chevron');
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : '';
  chev.style.transform = open ? 'rotate(-90deg)' : '';
}
// Collapse all-pass sections by default, keep failing ones open
document.querySelectorAll('.metric-header').forEach(h => {
  const badge = h.querySelector('.pass-badge');
  if (badge && badge.classList.contains('all-pass')) toggle(h);
});
</script>
</body>
</html>
""")
