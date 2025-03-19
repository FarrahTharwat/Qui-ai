# Start from a Python base image
FROM python:3.10

# Set the working directory inside the container
WORKDIR /apps

# Copy all project files into the container
COPY . /apps

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONPATH=/apps

# Start Celery worker
CMD ["celery", "-A", "apps.leaderboard.worker", "worker", "--loglevel=info"]
