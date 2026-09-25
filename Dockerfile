FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY data ./data
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
