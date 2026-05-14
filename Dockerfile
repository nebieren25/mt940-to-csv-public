FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY src ./src
COPY web-ui ./web-ui
COPY pyproject.toml README.md ./

USER app

EXPOSE 8181

CMD ["uvicorn", "src.web_app:app", "--host", "0.0.0.0", "--port", "8181"]
