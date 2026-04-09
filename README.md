# StudyGraph

StudyGraph is a LangGraph-based student exam preparation assistant.

## Run locally

1. Install dependencies (recommended with `uv`):

```bash
uv sync
```

2. Start the Streamlit app:

```bash
uv run streamlit run studygraph/ui/app.py
```

## Deployment

Live app (production): [https://study-graph-1018125388710.europe-west10.run.app/](https://study-graph-1018125388710.europe-west10.run.app/)

To deploy **StudyGraph** to **Google Cloud Run** (Docker image build/push, scaling, and Secret Manager), see **[docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md)**.

## Project status

Project initialized. Core agent features will be added incrementally.

