# Use official Python image
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY src/ .

CMD ["python", "scheduler.py"]