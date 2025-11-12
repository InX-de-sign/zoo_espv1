FROM python:3.11-bullseye

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && \
    apt-get install -y libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and models
COPY . .

EXPOSE 5000

CMD ["uvicorn", "model_api:app", "--host", "0.0.0.0", "--port", "5000"]