FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose FastAPI port
EXPOSE 8000

# Use CMD instead of ENTRYPOINT for flexibility
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
