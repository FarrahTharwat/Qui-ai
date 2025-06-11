FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy entire service into a subfolder under /app
COPY . /app/xp_points

# Install dependencies
RUN pip install --no-cache-dir -r /app/xp_points/requirements.txt

# Start FastAPI using full module path
CMD ["uvicorn", "xp_points.main:app", "--host", "0.0.0.0", "--port", "8000"]

