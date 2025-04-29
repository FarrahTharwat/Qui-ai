FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y libpq-dev gcc

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables for local development
ENV ENVIRONMENT="development"
ENV DB_USERNAME="farrahtharwat"
ENV DB_PASSWORD="farrahpost"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]