FROM python:3.10-slim

WORKDIR /app
COPY . /app/achievements


RUN pip install --no-cache-dir -r /app/achievements/requirements.txt

CMD ["uvicorn", "achievements.main:app", "--host", "0.0.0.0", "--port", "8000"]
