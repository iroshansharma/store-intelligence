FROM python:3.11-slim

# Enforce direct output streaming to prevent log buffering in Docker containers
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Install minimal OS requirements for OpenCV Headless and Curl diagnostics
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python package requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source tree
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]