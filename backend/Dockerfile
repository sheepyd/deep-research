FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock alembic.ini /app/
COPY alembic /app/alembic
COPY app /app/app
RUN uv sync --frozen --no-dev

EXPOSE 8000
