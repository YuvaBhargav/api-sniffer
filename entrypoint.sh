#!/bin/bash
set -e

echo "🛰️ Starting Self-Hosted API Request Sniffer..."
echo "Listener API Port: ${API_PORT:-5000}"
echo "Streamlit UI Port: ${STREAMLIT_SERVER_PORT:-8501}"

# Launch Streamlit (which also boots up the Flask listener thread inside app.py)
exec streamlit run app.py --server.port=${STREAMLIT_SERVER_PORT:-8501} --server.address=0.0.0.0
