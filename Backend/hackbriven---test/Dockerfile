FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend backend
COPY frontend frontend
COPY app.py .

ENV STORAGE_DIR=/app/storage/jobs
RUN mkdir -p /app/storage/jobs

EXPOSE 7860

CMD ["python", "app.py"]
