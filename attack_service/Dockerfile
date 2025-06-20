# Receives /launch, writes to PostGIS and emits first track point
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY *.py .

# Expose ports
EXPOSE 8000 9000

# Run the attack service
CMD ["python", "main.py"]