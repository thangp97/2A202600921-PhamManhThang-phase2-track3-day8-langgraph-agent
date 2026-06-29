"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

from pydantic import BaseModel

from .llm import get_llm
from .state import AgentState, make_event


class Classification(BaseModel):
    """Structured output schema for classify_node."""

    route: str        # one of: simple, tool, missing_info, risky, error
    risk_level: str   # "high" for risky route, else "low"


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── TODO(student): implement ALL nodes below ────────────────────────


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM.

    *** MUST use a real LLM call — keyword-only heuristics will lose points. ***

    Use .with_structured_output() or equivalent to get reliable enum classification.
    The LLM should classify into one of: simple, tool, missing_info, risky, error.

    Hints:
    - See llm.py for the get_llm() helper
    - Use Pydantic model or TypedDict with .with_structured_output()
    - Set risk_level to "high" for risky routes, "low" otherwise
    - Priority guide: risky > tool > missing_info > error > simple

    Return: {"route": str, "risk_level": str, "events": [make_event(...)]}
    """
    llm = get_llm().with_structured_output(Classification)
    prompt = (
        "You classify a customer support ticket into EXACTLY ONE route.\n"
        "Apply this priority order (higher wins if several seem to fit):\n"
        "1. risky  — actions with side effects: refund, delete, cancel, send email\n"
        "2. tool   — information lookups: order status, tracking, search\n"
        "3. missing_info — vague/incomplete, not enough context to act\n"
        "4. error  — system failures: timeout, crash, cannot recover\n"
        "5. simple — general questions answerable without tools/actions\n"
        "Set risk_level='high' only for the risky route, else 'low'.\n"
        f"Ticket: {state.get('query', '')}"
    )
    result = llm.invoke(prompt)
    return {
        "route": result.route,
        "risk_level": result.risk_level,
        "events": [make_event("classify", "completed", f"route={result.route}")],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.

    Requirements:
    - Read current attempt count from state
    - If route is "error" and attempt < 2: return error result (string containing "ERROR")
    - Otherwise: return a mock success result string
    - Append result to tool_results list

    Return: {"tool_results": [result_string], "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0)
    if state.get("route") == "error" and attempt < 2:
        result = f"ERROR: transient tool failure (attempt {attempt})"
    else:
        result = f"tool success for: {state.get('query', '')[:40]}"
    return {"tool_results": [result],
            "events": [make_event("tool", "completed", result)]}

def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.

    SHOULD use LLM-as-judge for bonus points. Heuristic (e.g., check for "ERROR" substring)
    is acceptable for base score.

    Requirements:
    - Read the latest entry from tool_results
    - Set evaluation_result to "needs_retry" or "success"
    - This field drives route_after_evaluate conditional edge

    Note: You may need to add 'evaluation_result' to AgentState if not present.

    Return: {"evaluation_result": str, "events": [make_event(...)]}
    """
    results = state.get("tool_results", [])
    latest = results[-1] if results else ""
    verdict = "needs_retry" if "ERROR" in latest else "success"
    return {"evaluation_result": verdict,
            "events": [make_event("evaluate", "completed", f"verdict={verdict}")]}

def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM.

    *** MUST use a real LLM call — hardcoded strings will lose points. ***

    The LLM should generate a helpful response grounded in available context:
    - tool_results (if any)
    - approval decision (if risky route)
    - original query

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    llm = get_llm()
    context = "\n".join(state.get("tool_results", [])) or "(no tool data)"
    approval = state.get("approval")
    prompt = (
        "You are a customer-support agent. Write a concise, helpful reply.\n"
        f"User question: {state.get('query', '')}\n"
        f"Tool results / context:\n{context}\n"
        + (f"Approval decision: {approval}\n" if approval else "")
        + "Ground your answer in the context above; do not invent facts."
    )
    answer = llm.invoke(prompt).content
    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    Generate a specific clarification question based on the vague/incomplete query.

    Note: You may need to add 'pending_question' to AgentState if not present.

    Return: {"pending_question": str, "final_answer": str, "events": [make_event(...)]}
    """
    question = "Bạn có thể cung cấp thêm chi tiết (mã đơn, thao tác cụ thể) không?"
    return {"pending_question": question, "final_answer": question,
            "events": [make_event("clarify", "completed", "asked clarification")]}

def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval.

    Describe the proposed action and why it requires approval.

    Note: You may need to add 'proposed_action' to AgentState if not present.

    Return: {"proposed_action": str, "events": [make_event(...)]}
    """
    action = f"Proposed risky action for: {state.get('query', '')[:60]}"
    return {"proposed_action": action,
            "events": [make_event("risky_action", "completed", action)]}

def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default behavior: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt() for real HITL.

    Return: {"approval": {"approved": bool, "reviewer": str, "comment": str}, "events": [make_event(...)]}
    """
    decision = {"approved": True, "reviewer": "mock-reviewer", "comment": "auto-approved"}
    return {
        "approval": decision,
        "events": [make_event("approval", "completed", "approved=True")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.

    Requirements:
    - Read current attempt from state, increment by 1
    - Add an error message to errors list
    - Return updated attempt count

    Return: {"attempt": int, "errors": [str], "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0) + 1
    return {
        "attempt": attempt,
        "errors": [f"retry attempt {attempt}"],
        "events": [make_event("retry", "completed", f"attempt={attempt}")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.

    This is the third layer: retry → fallback → dead letter.
    Log the failure and set a final_answer explaining that the request could not be completed.

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    msg = "Không thể hoàn tất yêu cầu sau số lần thử tối đa. Đã chuyển sang dead-letter."
    return {
        "final_answer": msg,
        "events": [make_event("dead_letter", "failed", msg)],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END.

    Return: {"events": [make_event("finalize", "completed", "workflow finished")]}
    """
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
