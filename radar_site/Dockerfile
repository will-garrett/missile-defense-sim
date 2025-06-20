# Subscribes to track_sim → applies PostGIS range checks → NATS publishes detections
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY radar_site.py .

CMD ["python", "radar_site.py"]