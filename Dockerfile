FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for XGBoost
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY labdx_api.py .
COPY citations.json .

# Copy the models folder
COPY models/ ./models/

# Expose the port
EXPOSE 8000

# Run the API
CMD ["uvicorn", "labdx_api:app", "--host", "0.0.0.0", "--port", "8000"]
