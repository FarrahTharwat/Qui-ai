FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libmupdf-dev \
    python3-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies with separate layer for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ML models during build
RUN python -c "from transformers import pipeline; pipeline('text2text-generation', model='google/flan-t5-base')"

# Copy application code
COPY . .

EXPOSE 8000

# Use production server with workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]