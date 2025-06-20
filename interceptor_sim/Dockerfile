

# Interceptor simulation: subscribes to intercept orders and publishes detonation events
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY interceptor_sim.py .

ENV PYTHONUNBUFFERED=1
CMD ["python", "interceptor_sim.py"]