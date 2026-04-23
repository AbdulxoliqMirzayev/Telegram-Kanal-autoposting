FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/posted_news.sqlite3
ENV TELETHON_SESSION_PATH=/app/data/session.session

RUN mkdir -p /app/data

CMD ["python", "main.py"]
