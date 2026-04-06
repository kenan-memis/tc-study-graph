# StudyGraph – AGENTS Guide

## Project overview

StudyGraph is a student-focused exam preparation assistant built for Turing College AI Engineering Sprint 3.
It helps learners create study plans, practice with quizzes, and improve weak topics over time using a LangGraph-based workflow.

## Tech stack and tools

- Language: Python 3.11+
- Package and environment management: **uv** (required)
- UI: Streamlit
- Agent orchestration: LangGraph + LangChain
- LLM: OpenAI API
- Data validation: Pydantic

## Core architecture principles

- LangGraph is the main orchestration layer (not only a linear chain).
- The app uses structured state for graph execution.
- The app includes both short-term session state and long-term memory persistence.
- Keep logic modular: `graph/`, `tools/`, `memory/`, `ui/`.

## Conventions and rules

1. **Use uv for everything**
   - Add dependencies with `uv add ...`
   - Install/sync with `uv sync`
   - Run commands with `uv run ...`
   - Do not use `pip install` directly.

2. **Secrets and security**
   - Keep API keys in `.env` only.
   - Never commit secrets.
   - `.env` must stay in `.gitignore`.

3. **Scope control**
   - Implement MVP features first.
   - Optional features are added only after MVP is stable.
   - Avoid over-engineering early.

4. **Reliability**
   - Add input validation and clear user-facing error messages.
   - Use safe fallbacks when model/tool output is malformed.

5. **Testing baseline**
   - Include unit tests for core logic and memory functions.
   - Include at least one graph smoke test with mocked model/tool outputs.

## Suggested run commands

```bash
uv sync
uv run streamlit run studygraph/ui/app.py
uv run pytest
```

