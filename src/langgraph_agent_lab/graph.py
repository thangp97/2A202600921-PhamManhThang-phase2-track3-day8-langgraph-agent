"""Graph construction.

This module is intentionally import-safe. It imports LangGraph only inside the builder so unit tests
that check schema/metrics can run even if students are still debugging graph wiring.
"""

from __future__ import annotations

from typing import Any

from .state import AgentState


def build_graph(checkpointer: Any | None = None):
    """Build and compile the LangGraph workflow.

    TODO(student): Build the complete graph with this architecture:

    START → intake → classify → [conditional: route_after_classify]
      simple       → answer → finalize → END
      tool         → tool → evaluate → [conditional: route_after_evaluate]
                                          success → answer → finalize → END
                                          needs_retry → retry → [conditional: route_after_retry]
                                                                  tool (retry)
                                                                  dead_letter → finalize → END
      missing_info → clarify → finalize → END
      risky        → risky_action → approval → [conditional: route_after_approval]
                                                  approved → tool → evaluate → ...
                                                  rejected → clarify → finalize → END
      error        → retry → [conditional: route_after_retry] → ...

    Steps:
    1. Import StateGraph, START, END from langgraph.graph
    2. Create StateGraph(AgentState)
    3. Import and add all nodes from nodes.py (11 nodes total)
    4. Import and use routing functions from routing.py for conditional edges
    5. Add fixed edges (e.g., START→intake, intake→classify, tool→evaluate, etc.)
    6. Add conditional edges using add_conditional_edges()
    7. Compile with checkpointer: graph.compile(checkpointer=checkpointer)

    Reference: https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/
    """
    from langgraph.graph import END, START, StateGraph

    from . import nodes, routing

    g = StateGraph(AgentState)

    # 1) Đăng ký 11 node (tên node = chuỗi mà routing trả về)
    g.add_node("intake", nodes.intake_node)
    g.add_node("classify", nodes.classify_node)
    g.add_node("tool", nodes.tool_node)
    g.add_node("evaluate", nodes.evaluate_node)
    g.add_node("answer", nodes.answer_node)
    g.add_node("clarify", nodes.ask_clarification_node)
    g.add_node("risky_action", nodes.risky_action_node)
    g.add_node("approval", nodes.approval_node)
    g.add_node("retry", nodes.retry_or_fallback_node)
    g.add_node("dead_letter", nodes.dead_letter_node)
    g.add_node("finalize", nodes.finalize_node)

    # 2) Cạnh cố định
    g.add_edge(START, "intake")
    g.add_edge("intake", "classify")
    g.add_edge("tool", "evaluate")          # gọi tool xong luôn đánh giá
    g.add_edge("risky_action", "approval")  # hành động rủi ro -> chờ duyệt
    g.add_edge("clarify", "finalize")
    g.add_edge("dead_letter", "finalize")
    g.add_edge("answer", "finalize")
    g.add_edge("finalize", END)

    # 3) Cạnh có điều kiện (dùng hàm routing)
    g.add_conditional_edges(
        "classify", routing.route_after_classify,
        ["answer", "tool", "clarify", "risky_action", "retry"],
    )
    g.add_conditional_edges("evaluate", routing.route_after_evaluate, ["retry", "answer"])
    g.add_conditional_edges("retry", routing.route_after_retry, ["tool", "dead_letter"])
    g.add_conditional_edges("approval", routing.route_after_approval, ["tool", "clarify"])

    return g.compile(checkpointer=checkpointer)
