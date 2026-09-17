FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure executable permissions for entrypoint script
RUN chmod +x entrypoint.sh

# Expose listener port (5000) and Streamlit dashboard port (8501)
EXPOSE 5000 8501

# Environment variables
ENV API_PORT=5000
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/healthz || exit 1

ENTRYPOINT ["./entrypoint.sh"]
