# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Day 08 lab: a LangGraph support-ticket agent (state, conditional routing, retry loop, HITL approval, persistence, metrics). It ships as a **starter skeleton** — node implementations, routing logic, and graph wiring are marked `TODO(student)` and must be built from scratch. See `README.md` and `docs/LAB_GUIDE.md` for the full assignment.

Python ≥3.11, package `langgraph_agent_lab` under `src/`. CLI entrypoint: `langgraph_agent_lab.cli` (also `agent-lab`).

## Commands

Standard `pytest` / `ruff` / `mypy` work, but prefer the Makefile targets — some are non-obvious:

- `make run-scenarios` — runs `data/sample/scenarios.jsonl` through the graph → `outputs/metrics.json` (`cli run-scenarios --config configs/lab.yaml`)
- `make grade-local` — validates `outputs/metrics.json` schema (`cli validate-metrics`)
- `make test` / `make lint` (`ruff check src tests`) / `make typecheck` (`mypy src`)
- Run a single test: `pytest -k test_name`

## LLM setup (required)

Nodes must make real LLM calls. `get_llm()` in `src/langgraph_agent_lab/llm.py` picks the provider from env keys, in order: `GEMINI_API_KEY` → `OPENAI_API_KEY` → `ANTHROPIC_API_KEY`. Configure `.env` (copy `.env.example`) and install the matching extra: `pip install -e '.[google]'` / `'.[openai]'` / `'.[anthropic]'`. Override the model with `LLM_MODEL`. SQLite persistence needs `'.[sqlite]'`.

## Code style

- ruff: line-length 100, target py311, rules `E,F,I,B,UP,N,ANN` (type annotations enforced; `ANN101`/`ANN102` ignored). Annotate function signatures.
- mypy runs on `src` — keep state serializable and typed.

## Lab gotchas

- **Never hard-code routes by scenario id** — classify with the LLM; grading uses hidden scenarios.
- `classify_node` must use `.with_structured_output(Model)`; raw text parsing fails on hidden cases.
- Route priority: `risky > tool > missing_info > error > simple`.
- Bound the retry loop (`attempt < max_attempts`) or error scenarios loop forever.
- Every path must reach `finalize → END`, or the graph hangs.
- SqliteSaver 3.x API: `SqliteSaver(conn=sqlite3.connect(...))`, not `from_conn_string()`.
- `AgentState` intentionally omits fields — add `evaluation_result`, `pending_question`, `proposed_action`, `approval` as you implement the nodes that need them.
