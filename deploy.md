# Deploying to Google Cloud Run Jobs

A runbook for getting the AI-company orchestrator running on GCP. The
target shape is **Cloud Run Job triggered by Cloud Scheduler**: the CEO
runs to completion on a schedule (or on demand), with no HTTP server.

```
Cloud Scheduler ─cron─▶ Cloud Run Job ─reads─▶ Secret Manager (API keys)
                            │
                            ├─writes─▶ Cloud Logging (run output)
                            └─writes─▶ Supabase Postgres (memory) [later]
```

## What you need before starting

- A GCP project with billing enabled.
- `gcloud` CLI authenticated (`gcloud auth login`).
- An `ANTHROPIC_API_KEY`.
- ~10 minutes.

## One-time setup

Set vars used by the rest of this doc:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export REPO="acme"
export IMAGE="acme-ai-company"
export JOB="acme-ceo"

gcloud config set project "$PROJECT_ID"
```

Enable the APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com
```

Create the Artifact Registry repo (one-time):

```bash
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="AI company images"
```

Store the Anthropic key in Secret Manager:

```bash
echo -n "sk-ant-..." | gcloud secrets create anthropic-api-key \
  --replication-policy=automatic \
  --data-file=-
```

## Build and push the image

Use Cloud Build (no local Docker needed):

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_JOB="$JOB",_IMAGE="$IMAGE"
```

The first run will fail at the `deploy` step because the job doesn't exist
yet — that's expected. Create it next, then re-run.

## Create the Cloud Run Job

```bash
gcloud run jobs create "$JOB" \
  --region="$REGION" \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE:latest" \
  --task-timeout=30m \
  --max-retries=1 \
  --set-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars=REQUIRE_APPROVAL=false,GOAL="Daily standup: what changed yesterday across the company?"
```

Notes:
- `--task-timeout=30m`: a single CEO turn can take 5–15 min with multiple
  tool calls. Don't set this too low.
- `--max-retries=1`: agent runs are not idempotent — don't auto-retry on
  failure or you'll get duplicate work.
- `REQUIRE_APPROVAL=false`: required for unattended runs (no TTY for the
  CLI approver). Replace with a Slack approver before flipping back on.
- `GOAL`: the prompt the CEO will work on. Override per-execution below.

## Run it once, manually

```bash
gcloud run jobs execute "$JOB" --region="$REGION" --wait
```

Tail the output:

```bash
gcloud beta run jobs executions logs read \
  $(gcloud run jobs executions list --job="$JOB" --region="$REGION" \
      --limit=1 --format='value(name)') \
  --region="$REGION"
```

## Run with a different goal

To override the goal for a one-off execution:

```bash
gcloud run jobs execute "$JOB" --region="$REGION" --wait \
  --update-env-vars=GOAL="Draft a launch plan for our v1 developer product"
```

## Schedule a daily run (Cloud Scheduler)

The Cloud Scheduler service account needs `roles/run.invoker` on the job:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud run jobs add-iam-policy-binding "$JOB" \
  --region="$REGION" \
  --member="serviceAccount:$SA" \
  --role="roles/run.invoker"
```

Create the schedule (daily 9am UTC):

```bash
gcloud scheduler jobs create http acme-daily-standup \
  --location="$REGION" \
  --schedule="0 9 * * *" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run" \
  --http-method=POST \
  --oauth-service-account-email="$SA"
```

## Updating the deployment

Push code → re-run Cloud Build:

```bash
git push origin claude/ai-agents-company-setup-xZg6V

gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_JOB="$JOB",_IMAGE="$IMAGE"
```

The pipeline rebuilds the image and updates the Job in place.

For full GitHub automation, create a Cloud Build trigger:

```bash
gcloud builds triggers create github \
  --name=acme-deploy-on-push \
  --repo-name=my-ai-company \
  --repo-owner=bluefalcon2357 \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

## Cost expectations

At the recommended size (1 vCPU, 512Mi memory, ~5 runs/day, 5 min each):

| Component | Approx monthly |
|---|---|
| Cloud Run Jobs (compute) | $0–$2 |
| Artifact Registry storage | $0.10 |
| Secret Manager | $0.06 |
| Cloud Logging (default retention) | $0–$1 |
| Cloud Scheduler | free tier covers it |
| **Anthropic API tokens** | **dominates everything else — $20–$500+ depending on activity** |

Watch tokens; the GCP infra is essentially free.

## Operational notes

- **Memory backend**: SQLite inside the container is **ephemeral** — every
  execution starts fresh. Migrate `Memory` to Postgres (Supabase or Cloud
  SQL) before relying on cross-run state. See `src/memory.py`.
- **Approvals**: `REQUIRE_APPROVAL=false` is safe only because no
  department has real-world write tools yet. Before adding GitHub MCP,
  Stripe, etc., implement a Slack approver and flip it back on.
- **Concurrency**: Cloud Run Jobs run one task at a time by default. Don't
  raise `--parallelism` until your memory backend supports concurrent
  writes from multiple instances.
- **Secrets rotation**: add new versions with
  `gcloud secrets versions add anthropic-api-key --data-file=-`. Job picks
  up the new version on next execution (`:latest` in the secret ref).
- **Killing a runaway run**:
  ```bash
  gcloud run jobs executions cancel <execution-name> --region="$REGION"
  ```

## Next steps

1. Replace the `CLIApprover` in `src/approvals.py` with a Slack-webhook
   approver that posts an interactive Block Kit message.
2. Migrate `Memory` from SQLite to Supabase Postgres.
3. Wire one real backend tool (GitHub MCP, sandbox repo) for Engineering.
4. Add Langfuse tracing for cost and reasoning visibility.
5. Set a daily token budget; bail the CEO if exceeded.
