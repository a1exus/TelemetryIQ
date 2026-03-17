# TelemetryIQ — Python 3.14+ for gt-telem
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default DB location for Docker volume mount
RUN mkdir -p /data

CMD ["python", "-m", "rexy"]
