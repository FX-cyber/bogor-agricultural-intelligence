FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PUBLIC_DEPLOYMENT=true
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY app ./app
COPY scripts ./scripts
COPY data/snapshot ./data/snapshot
RUN mkdir -p /app/data/cache && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
# One worker/replica: the BPS refresh lock and request budget are process-local.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
