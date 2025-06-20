# Polls PostGIS, simulates each missile’s flight, republishes refined track points
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY track_sim.py .

CMD ["python", "track_sim.py"]