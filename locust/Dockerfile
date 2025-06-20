# Master & Worker share this image; installs any extra load-test deps you need
FROM locustio/locust:latest

# Copy your locustfile(s) & configs
WORKDIR /mnt/locust
COPY . /mnt/locust

# Install additional Python libs for your load scripts (if needed)
COPY requirements.txt /tmp/requirements.txt
RUN if [ -s /tmp/requirements.txt ]; then pip install --no-cache-dir -r /tmp/requirements.txt; fi

# Default entrypoint runs in either master or worker mode based on LOCUST_MODE
CMD ["locust", "-f", "locustfile.py", "--host", "${LOCUST_HOST}"]