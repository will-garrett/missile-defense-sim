# NATS-subscriber for detections → correlates → issues battery intercept orders
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY command_center.py .

CMD ["python", "command_center.py"]