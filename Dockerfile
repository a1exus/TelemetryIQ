# GT7 telemetry app — Python 3.10+ for gt-telem
FROM python:3.14-slim

WORKDIR /app

# Application code + install
COPY . .
RUN pip install --no-cache-dir .

# Default: run telemetry client (override in compose or CLI)
CMD ["rexy"]
