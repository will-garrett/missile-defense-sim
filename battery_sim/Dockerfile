# Subscribes to battery.intercept → simulates interceptor flight → records hits/misses
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY battery_sim.py .

CMD ["python", "battery_sim.py"]