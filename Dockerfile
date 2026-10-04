FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Backend/hackbriven---test/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/hackbriven---test/backend backend
COPY Backend/hackbriven---test/run_api.py .

ENV STORAGE_DIR=/app/storage/jobs \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000
RUN mkdir -p /app/storage/jobs

EXPOSE 8000

CMD ["python", "run_api.py"]
