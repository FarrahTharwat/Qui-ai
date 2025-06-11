FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy entire service into a subfolder under /app
COPY . /app/track_progress

# Install dependencies
RUN pip install --no-cache-dir -r /app/track_progress/requirements.txt

# Start FastAPI using full module path
CMD ["uvicorn", "track_progress.main:app", "--host", "0.0.0.0", "--port", "8000"]

