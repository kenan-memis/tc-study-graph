# Deploy StudyGraph to Google Cloud Run

**Production:** [https://study-graph-1018125388710.europe-west10.run.app/](https://study-graph-1018125388710.europe-west10.run.app/)

---

This guide assumes you already have:

- A **GCP project** with billing enabled  
- **APIs enabled** (minimum): Cloud Run, Artifact Registry, Secret Manager  
- **Secrets created** in Secret Manager for the API keys the app reads from the environment:  
  - `OPENAI_API_KEY`  
  - `GEMINI_API_KEY`  

The Streamlit app loads keys with `python-dotenv` **and** `os.getenv`. In Cloud Run you inject secrets as **environment variables** (no `.env` file in the image).

---

## 1. Files in this repo

| File | Purpose |
|------|---------|
| `Dockerfile` | `python:3.13-slim`, `uv sync --frozen --no-dev`, entrypoint |
| `docker-entrypoint.sh` | Runs Streamlit on `0.0.0.0` and `$PORT` (default `8080`) |
| `.dockerignore` | Keeps `.venv`, tests, local `data/memory`, `.env`, etc. out of the image |

---

## 2. Local sanity check (optional)

From the `study-graph/` directory (same folder as `Dockerfile`):

```bash
chmod +x docker-entrypoint.sh
docker build -t study-graph:local .
docker run --rm -p 8080:8080 \
  -e OPENAI_API_KEY="your-key" \
  -e GEMINI_API_KEY="your-key" \
  study-graph:local
```

Open `http://localhost:8080`. Press `Ctrl+C` to stop.

---

## 3. Configure gcloud

Set your project and a default region (example: `europe-west1`):

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west1"

gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
```

---

## 4. Artifact Registry repository

Create a Docker repository (once per project):

```bash
export REPO="study-graph"

gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="StudyGraph containers" \
  || true
```

Configure Docker to authenticate to Artifact Registry:

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
```

---

## 5. Build, tag, and push the image

From the repo root (`study-graph/`), where `Dockerfile` lives:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west1"
export REPO="study-graph"
export IMAGE_NAME="study-graph"
export TAG="v1"   # or $(git rev-parse --short HEAD)

export IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"

docker build --platform linux/amd64 -t "$IMAGE_URI" .
docker push "$IMAGE_URI"
```

### Build for `linux/amd64` (Apple Silicon / M-series Macs)

**Cloud Run expects a linux/amd64 image.** If you build on an **Apple Silicon Mac** (M1/M2/M3), Docker often produces **arm64** (or a multi-arch **OCI image index**). Deploying that image can fail with:

`Container manifest type 'application/vnd.oci.image.index.v1+json' must support amd64/linux`

Always pass **`--platform linux/amd64`** when building the image you push for Cloud Run. On Intel/AMD machines the flag is still valid and matches what Cloud Run runs.

Optional one-step build and push with Buildx:

```bash
docker buildx build --platform linux/amd64 -t "$IMAGE_URI" --push .
```

---

## 6. Deploy to Cloud Run

Pick a **service name** and wire **Secret Manager** secrets to **environment variables**.  
Replace secret names below with the names you created in Secret Manager (examples: `openai-api-key`, `gemini-api-key`).

```bash
export SERVICE="study-graph"
export IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"

gcloud run deploy "$SERVICE" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest"
```

Notes:

- **`--set-secrets`** format is `ENV_VAR=secret-name:version`. Adjust secret **resource names** to match your project.  
- If you only use one provider in production, you can still mount both secrets; the app treats missing keys as “fallback mode” for that provider.  
- For **authenticated** access only, omit `--allow-unauthenticated` and grant `roles/run.invoker` to users or service accounts.

After deploy, the command prints the **service URL**.

---

## 7. Redeploy after code changes

Rebuild, push with a new tag, deploy again:

```bash
export TAG="v2"
export IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"
docker build --platform linux/amd64 -t "$IMAGE_URI" .
docker push "$IMAGE_URI"

gcloud run deploy "$SERVICE" --image="$IMAGE_URI" --region="$REGION"
```

---

## 8. Persistence caveat

Profiles and session data are stored under `data/memory/` on the container filesystem. **Cloud Run instances are ephemeral**; data is lost when the instance is recycled unless you add **persistent storage** (e.g. Cloud Storage–backed state or a database). For a course demo, empty storage on each cold start is often acceptable.

---

## 9. Troubleshooting

| Issue | What to check |
|--------|----------------|
| `must support amd64/linux` / OCI image index | Rebuild with **`docker build --platform linux/amd64`** (see §5) and push again; common on Apple Silicon Macs |
| Container exits immediately | Cloud Run logs: `gcloud run services logs read "$SERVICE" --region="$REGION"` |
| 502 / app not listening | Streamlit must bind `0.0.0.0` and use `$PORT` (see `docker-entrypoint.sh`) |
| Missing API keys | Secret names/versions in `--set-secrets` and IAM for the Cloud Run service account (`roles/secretmanager.secretAccessor` on those secrets) |
| Image pull errors | Image URI, Artifact Registry permissions, `docker push` succeeded |

---

## 10. IAM for Secret Manager

The Cloud Run **runtime service account** (default is `PROJECT_NUMBER-compute@developer.gserviceaccount.com` unless you override) needs access to the secrets. When you use `--set-secrets`, Cloud Run usually grants access automatically; if deployment fails with permission errors, add **Secret Manager Secret Accessor** on those secrets for that service account.
