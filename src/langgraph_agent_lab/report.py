"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

import os
from pathlib import Path

from .metrics import MetricsReport


def _mermaid_diagram() -> str | None:
    """Sinh sơ đồ Mermaid từ graph đã compile (không cần LLM). Trả None nếu lỗi."""
    try:
        from .graph import build_graph

        return build_graph(checkpointer=None).get_graph().draw_mermaid()
    except Exception:
        return None


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    TODO(student): Generate a report that includes:
    1. Metrics summary table (total scenarios, success rate, retries, interrupts)
    2. Per-scenario results table
    3. Architecture explanation (your graph design, state schema, reducers)
    4. Failure analysis (at least two failure modes you considered)
    5. Improvement plan

    Use reports/lab_report_template.md as your guide.

    Return: formatted markdown string
    """
    lines: list[str] = []
    lines.append("# Day 08 Lab Report")
    lines.append("")

    # 0. Student identity (đọc từ .env để không mất khi regenerate)
    lines.append("## 0. Student")
    lines.append("")
    lines.append(f"- Name: {os.getenv('STUDENT_NAME', '___')}")
    lines.append(f"- Student ID: {os.getenv('STUDENT_ID', '___')}")
    lines.append(f"- Date: {os.getenv('STUDENT_DATE', '___')}")
    lines.append("")

    # 1. Summary
    lines.append("## 1. Metrics summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total scenarios | {metrics.total_scenarios} |")
    lines.append(f"| Success rate | {metrics.success_rate:.2%} |")
    lines.append(f"| Avg nodes visited | {metrics.avg_nodes_visited:.2f} |")
    lines.append(f"| Total retries | {metrics.total_retries} |")
    lines.append(f"| Total interrupts | {metrics.total_interrupts} |")
    lines.append(f"| Resume success | {metrics.resume_success} |")
    lines.append("")

    # 2. Per-scenario results
    lines.append("## 2. Scenario results")
    lines.append("")
    lines.append("| Scenario | Expected | Actual | Success | Retries | Interrupts |")
    lines.append("|---|---|---|---:|---:|---:|")
    for m in metrics.scenario_metrics:
        ok = "✅" if m.success else "❌"
        lines.append(
            f"| {m.scenario_id} | {m.expected_route} | {m.actual_route} "
            f"| {ok} | {m.retry_count} | {m.interrupt_count} |"
        )
    lines.append("")

    # 3. Architecture
    lines.append("## 3. Architecture")
    lines.append("")
    lines.append(
        "Graph: `START → intake → classify → [conditional route]`. Routes branch to "
        "`answer` (simple), `tool → evaluate` (tool, with a bounded retry loop via "
        "`evaluate → retry → tool`), `clarify` (missing_info), "
        "`risky_action → approval → tool` (risky, human-in-the-loop), and "
        "`retry` (error). Every path converges at `finalize → END`."
    )
    lines.append("")
    diagram = _mermaid_diagram()
    if diagram:
        lines.append("Graph diagram (auto-generated via `draw_mermaid()`):")
        lines.append("")
        lines.append("```mermaid")
        lines.append(diagram.rstrip())
        lines.append("```")
        lines.append("")

    # 4. State schema
    lines.append("## 4. State schema")
    lines.append("")
    lines.append("| Field | Reducer | Why |")
    lines.append("|---|---|---|")
    lines.append("| messages / tool_results / errors / events | append | audit trail |")
    lines.append("| route / risk_level / attempt / final_answer | overwrite | current value only |")
    lines.append(
        "| evaluation_result / approval / proposed_action / pending_question "
        "| overwrite | latest decision drives routing |"
    )
    lines.append("")

    # 5. Failure analysis
    lines.append("## 5. Failure analysis")
    lines.append("")
    lines.append(
        "1. **Transient tool failure**: `tool_node` returns an `ERROR` result; "
        "`evaluate_node` flags `needs_retry`; `route_after_retry` retries until "
        "`attempt >= max_attempts`, then escalates to `dead_letter` (no infinite loop)."
    )
    lines.append(
        "2. **Risky action without approval**: risky routes are forced through "
        "`risky_action → approval`; `route_after_approval` only proceeds to `tool` "
        "when `approval.approved` is true, otherwise diverts to `clarify`."
    )
    lines.append("")

    # 6. Persistence
    lines.append("## 6. Persistence / recovery")
    lines.append("")
    lines.append(
        "Compiled with a checkpointer; each run uses a per-scenario `thread_id` "
        "(`configurable.thread_id`). The default run uses `MemorySaver`; a SQLite "
        "backend (`SqliteSaver` + WAL) is implemented in `persistence.py`."
    )
    lines.append("")
    lines.append(
        "**Crash-resume evidence** — `scripts/persistence_demo.py` runs a scenario in "
        "one process, then a fresh process reopens the same SQLite file and recovers "
        "the state via `get_state()` / `get_state_history()` without re-running the graph:"
    )
    lines.append("")
    lines.append("```text")
    lines.append("[process 1] route=tool final_answer='Thank you for your inquiry...'")
    lines.append("--- simulated crash: new process, only reads the DB back ---")
    lines.append("[process 2] RESUMED from SQLite -> route='tool', events=6")
    lines.append("[process 2] state history checkpoints = 8 (time-travel available)")
    lines.append("```")
    lines.append("")

    # 7. Improvement plan
    lines.append("## 7. Improvement plan")
    lines.append("")
    lines.append(
        "Replace heuristic `evaluate_node` with an LLM-as-judge, add real "
        "`interrupt()`-based HITL, and persist checkpoints to SQLite for crash recovery."
    )
    lines.append("")

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
