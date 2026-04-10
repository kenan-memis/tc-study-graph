# StudyGraph

StudyGraph is a **LangGraph**-based student study and exam preparation assistant with a **Streamlit** UI. It is built for **Sprint 3** of the Turing College AI Engineering course: students define a course, topic, and goals; the app generates study plans, material, quizzes, and recommendations, with optional feedback and usage tracking.

---

## What it is for

- Help learners **structure study sessions** with generated plans and supporting material.
- Support **OpenAI** and **Gemini** as LLM providers, with persisted **temperature / top-p** and provider choice.
- Record **session history**, **weak topics**, and **optional thumbs-up/down feedback** per profile (JSON on disk under `data/memory/` locally).

---

## How it is built

| Area | Stack |
|------|--------|
| **Language** | Python 3.11+ (see `pyproject.toml`; Docker image uses 3.13) |
| **Environment & deps** | [`uv`](https://github.com/astral-sh/uv) + `pyproject.toml` / `uv.lock` (no `requirements.txt`) |
| **UI** | [Streamlit](https://streamlit.io/) — single-page app |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) workflows for prepare / quiz / evaluation |
| **LLMs** | OpenAI & Google Gemini APIs (keys via env / Secret Manager in production) |
| **Config** | YAML in `studygraph/config/`, prompts in `studygraph/prompts/prompts.yaml` |

For optional-task implementation detail, see **[docs/OPTIONAL_TASKS.md](docs/OPTIONAL_TASKS.md)**.

---

## Project structure (early)

```text
study-graph/                 # repo root
├── README.md                # This file — what the app is, how to run it
├── pyproject.toml           # Dependencies (uv); package metadata
├── uv.lock                  # Locked versions for reproducible installs
├── Dockerfile               # Production image (Cloud Run / local)
├── docker-compose.yml       # Local Docker: Streamlit on :8080 + dev deps for lint/tests
├── docker-entrypoint.sh     # streamlit run … --server.address 0.0.0.0
├── .env.example             # Copy to `.env` for local keys (never commit `.env`)
├── docs/
│   ├── OPTIONAL_TASKS.md    # Sprint optional tasks — status & files
│   └── DEPLOY_GCP.md        # Cloud Run deploy (build, push, secrets, amd64)
├── studygraph/
│   ├── ui/app.py            # Streamlit entrypoint
│   ├── graph/workflow.py    # LangGraph graphs
│   ├── memory/store.py      # Profile + session JSON persistence
│   ├── prompts/             # Prompt loader + YAML overrides
│   └── config/              # UI constants & settings YAML + injected CSS
├── data/memory/             # Created at runtime (profiles, sessions); gitignored locally
└── tests/                   # pytest
```

---

## System dependencies

You need the following installed on your machine:

- **Git**
- **Docker** (Docker Desktop or Docker Engine **with Compose V2**: `docker compose …`)

Optional (runs tests/lint on the host without Docker):

- **[uv](https://github.com/astral-sh/uv)** — same lockfile as Docker

---

## Getting started

Clone the repository (replace with your fork or course remote):

```bash
git clone https://github.com/YOUR_ORG/study-graph.git
cd study-graph
```

---

## Configure API keys (local)

Copy the example env file and add your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```text
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=your_gemini_key_here
```

Keep **`.env` out of version control** (it is listed in `.gitignore`).

---

## Development (Docker)

From the repo root, with Docker running:

```bash
docker compose up -d
docker compose ps   # confirm the `app` service is up
```

The Compose file builds the image with **`INSTALL_DEV=true`** so the same image can run **lint** and **tests** (see below). Production images built with `docker build` alone use **`INSTALL_DEV=false`** (no dev deps) — see [docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md).

---

## Application up and running

Open the app in a browser:

**[http://localhost:8080](http://localhost:8080)**

(Streamlit listens on port **8080** inside the container, mapped to the host by Compose.)

---

## Linting

[Ruff](https://docs.astral.sh/ruff/) is configured in `pyproject.toml` (starts with **Pyflakes + E9** rules; you can widen `select` over time).

**Using Docker Compose** (same `app` service; override the Streamlit entrypoint):

```bash
docker compose run --rm --entrypoint "" app uv run ruff check studygraph tests
```

**Using uv on the host:**

```bash
uv sync --extra dev
uv run ruff check studygraph tests
```

---

## Running tests

Tests use **[pytest](https://pytest.org/)**.

**Using Docker Compose:**

```bash
docker compose run --rm --entrypoint "" app uv run pytest tests/
```

**Using uv on the host:**

```bash
uv sync --extra dev
uv run pytest tests/
```

---

## Run locally without Docker (optional)

```bash
uv sync
uv run streamlit run studygraph/ui/app.py
```

Use **Configure API keys** above so `python-dotenv` can load `.env`.

---

## Deployment

**Live app (production):** [https://study-graph-1018125388710.europe-west10.run.app/](https://study-graph-1018125388710.europe-west10.run.app/)

To deploy **StudyGraph** to **Google Cloud Run** (Docker build/push for **linux/amd64**, Artifact Registry, secrets, scaling), see **[docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md)**.

---

## Optional tasks (progress)

Checklist of Sprint 3 optional tasks. Marked with ✅ when implemented. For maximum bonus points, the goal is at least **2 medium** and **1 hard** (or more, depending on time). Details and file references: **[docs/OPTIONAL_TASKS.md](docs/OPTIONAL_TASKS.md)**.

### Easy

1. ✅ Ask ChatGPT to critique your solution from the usability, security, and prompt-engineering sides.
2. ✅ Give the agent a personality: tweak responses to make them more formal, friendly, or concise based on user needs.
3. ✅ Provide the user with the ability to choose from a list of LLMs (Gemini, OpenAI, etc.) for this project.
4. ✅ Add all of the OpenAI settings (temperature, top-p frequency) for the user to tune as sliders/fields.
5. ✅ Add an interactive help feature or chatbot guide.

### Medium

1. ✅ Calculate and display token usage and costs.
2. ✅ Add retry logic for agents.
3. ✅ Implement long-term or short-term memory in LangChain/LangGraph.
4. ✅ Implement one more function tool that would call an external API.
5. Add user authentication and personalisation.
6. ✅ Implement a caching mechanism to store and retrieve frequently used responses.
7. ✅ Implement a feedback loop where users can rate the responses, and use this feedback to improve the agent's performance.
8. Implement 2 extra function tools (5 in total). Have a UI for the user to either enable or disable these function tools. Develop a plugin system that allows users to add or remove functionalities from the chatbot dynamically.
9. ✅ Implement multi-model support (OpenAI, Anthropic, etc.).

### Hard

1. Agentic RAG: Think of a way to add RAG functionality to the LangChain/LangGraph application and implement it.
2. Add one of these LLM observability tools: Arize Phoenix, LangSmith, Lunary, or others.
3. Fine-tune the model for your specific domain.
4. Create an agent that can learn from user feedback. This agent should be able to adjust its capabilities based on the feedback to improve future performance.
5. Implement an agent that can integrate with external data sources to enrich its knowledge. This could involve fetching additional data from APIs or websites.
6. Implement an agent that can collaborate with other agents in a distributed system. This agent should be able to work with agents running on different machines or in different environments, coordinating their efforts to solve the problem efficiently.
7. ✅ Deploy your app to the cloud with proper scaling.

**Hard #4 and #5:** Partially covered by Medium work (feedback loop; Wikipedia / external context).

---

## License and course context

This project is part of the **Turing College AI Engineering** course (**Sprint 3** — building with AI agents / LangGraph). It is for **learning and portfolio** purposes.
