FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY company/ ./company/

# Cloud Run Jobs ignore CMD args; the orchestrator reads GOAL from env.
# Override at deploy time with: gcloud run jobs update ... --update-env-vars GOAL="..."
CMD ["python", "-m", "src.main"]
