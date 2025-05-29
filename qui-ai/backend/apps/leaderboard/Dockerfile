FROM python:3.10-slim

# Install required system dependencies
RUN apt-get update && \
    apt-get install -y curl gnupg lsb-release && \
    curl -sL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg && \
    echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/azure-cli.list && \
    apt-get update && \
    apt-get install -y azure-cli

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Set environment variables
ENV PYTHONPATH=/apps

# Start Celery worker
CMD ["celery", "-A", "worker", "worker", "--loglevel=info"]
