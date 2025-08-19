FROM python:3.11.4-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --prefix=/install -r requirements.txt

FROM python:3.11.4-slim
WORKDIR /app/src
COPY --from=builder /install /usr/local
COPY src/ .
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn", "-c", "gunicorn_conf.py", "-b", "0.0.0.0:8000", "app.main:app"] 