r"""Demo persistence SQLite: run 1 scenario, persist checkpoint, then open a brand-new
process (simulated crash) and read the state back from the same DB file.

Run: .\.venv\Scripts\python.exe scripts\persistence_demo.py
"""

from __future__ import annotations

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state

DB = "outputs/checkpoints.sqlite"
THREAD = "demo-thread-001"


def run_once() -> None:
    """Process 1: run the graph, write checkpoint into SQLite."""
    graph = build_graph(checkpointer=build_checkpointer("sqlite", DB))
    scenario = Scenario(id="DEMO", query="Please lookup order status for order 999",
                        expected_route=Route.TOOL)
    state = initial_state(scenario)
    state["thread_id"] = THREAD
    result = graph.invoke(state, config={"configurable": {"thread_id": THREAD}})
    print(f"[process 1] route={result['route']} final_answer={result['final_answer'][:50]!r}")


def resume_after_crash() -> None:
    """Process 2 (fresh): reopen the same DB, read the saved state without re-running."""
    graph = build_graph(checkpointer=build_checkpointer("sqlite", DB))
    cfg = {"configurable": {"thread_id": THREAD}}
    snapshot = graph.get_state(cfg)
    print(f"[process 2] RESUMED from SQLite -> route={snapshot.values.get('route')!r}, "
          f"events={len(snapshot.values.get('events', []))}")
    history = list(graph.get_state_history(cfg))
    print(f"[process 2] state history checkpoints = {len(history)} (time-travel available)")


if __name__ == "__main__":
    run_once()
    print("--- simulated crash: new process, only reads the DB back ---")
    resume_after_crash()
