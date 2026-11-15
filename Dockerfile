FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY knowledge ./knowledge
COPY config.yaml .
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1 SITE_DIR=/app/state/site
CMD ["python", "-m", "scalper.main", "--loop"]
