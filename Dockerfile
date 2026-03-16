# GT7 telemetry app — Python 3.10+ for gt-telem
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Default: run telemetry client (override in compose or CLI)
CMD ["python", "-m", "gt7"]
