# 🛰️ Self-Hosted API Request Sniffer & Inspection Dashboard

A lightweight, self-hosted API request sniffer and real-time inspection dashboard built with **Python**, **Streamlit**, and **Flask**. Designed to capture, log, inspect, replay, and mock incoming HTTP requests across all HTTP methods without hiding or truncating any parameters.

---

## ✨ Features

- **Full-Spectrum Request Capture**: Logs `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `HEAD` and custom HTTP methods across any subpath (`/*`).
- **Complete Parameter Inspection (Un-redacted)**:
  - **Query Parameters**: Full URL query strings and multi-value query array parsing (`?tag=a&tag=b`).
  - **Headers & Cookies**: Complete, un-redacted headers and cookie dictionary view.
  - **Payload & Body**: Automatic formatting for JSON, URL-encoded form data, raw text, and binary hex fallback.
  - **Multipart File Uploads**: Stores uploaded files in `./uploads/` with sanitized timestamped filenames, MD5 checksum calculation, image previews, and 1-click download buttons.
  - **Client Metadata**: Client IP address (with `X-Forwarded-For` support), User-Agent, Content-Type, Content-Length, ISO 8601 millisecond timestamps.
- **SQLite Persistence**: Thread-safe SQLite engine (`sniffer_logs.db`) ensuring logs persist across dashboard reruns and container restarts.
- **Real-Time Live Feed**: Streamlit dashboard with auto-refresh (1s, 2s, 5s, 10s, manual), method distribution statistics, search bar, and method filtering.
- **Dynamic Response Mocking**: Configure mock HTTP response status codes (`200`, `201`, `400`, `404`, `500`), custom JSON response bodies, custom response headers, and artificial latency simulation (0-3000ms delay).
- **Code Generators & Replay**:
  - Export captured requests as **cURL**, **Python `requests`**, or **JavaScript `fetch`**.
  - **1-Click Request Replay**: Interactively resend captured requests directly from the dashboard to any target endpoint.
- **Built-in API Sandbox / Request Tester**: Fire test GET/POST/PUT/DELETE requests right inside the sidebar to test your sniffer instantly.
- **Data Export & Management**: Download captured logs as **JSON** or **CSV**; clear all logs or delete single log entries.
- **Ready for Deployment**: Includes `Dockerfile`, `docker-compose.yml`, `render.yaml`, `Procfile`, and `entrypoint.sh`.

---

## 🚀 Quickstart

### 1. Local Run

```bash
# Clone repository and navigate to folder
cd api-sniffer

# Install dependencies
pip install -r requirements.txt

# Run Streamlit Application (starts both Flask listener on port 5000 & UI on port 8501)
streamlit run app.py
```

Open your browser at:
- **Inspection Dashboard**: `http://localhost:8501`
- **Listener Endpoint**: `http://localhost:5000/`

---

### 2. Run Synthetic Test Suite

While `app.py` is running, send test requests across all HTTP methods and multipart uploads:

```bash
python test_sniffer.py
```

---

### 3. Docker Deployment

Launch containerized instance with 1 command:

```bash
docker-compose up --build -d
```

- **Dashboard**: `http://localhost:8501`
- **Listener API**: `http://localhost:5000`

---

## 🧪 Example cURL Requests to Test Sniffer

```bash
# 1. GET Request with Query Parameters
curl -X GET "http://localhost:5000/api/v1/users?page=1&limit=20&tag=admin&tag=active"

# 2. POST Request with JSON Body
curl -X POST "http://localhost:5000/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer secret_token_123" \
  -d '{"order_id": "ORD-100", "price": 49.99}'

# 3. PUT Request
curl -X PUT "http://localhost:5000/api/v1/settings" \
  -d "mode=dark&notifications=true"

# 4. DELETE Request
curl -X DELETE "http://localhost:5000/api/v1/items/42"

# 5. Multipart File Upload
curl -X POST "http://localhost:5000/api/v1/upload" \
  -F "file=@sample.txt" \
  -F "author=Yuva"
```

---

## 🛠️ Configuration & Environment Variables

| Variable | Default | Description |
|---|---|---|
| `API_PORT` | `5000` | Port for the background Flask HTTP listener |
| `STREAMLIT_SERVER_PORT` | `8501` | Port for the Streamlit dashboard |
| `STREAMLIT_SERVER_ADDRESS` | `0.0.0.0` | Host binding for Streamlit |

---

## 📁 Repository Structure

```
.
├── app.py               # Main application (Flask listener thread + Streamlit UI)
├── db.py                # SQLite database persistence layer & un-redacted logging
├── api_streamlit.py     # Backward-compatible entrypoint wrapper
├── test_sniffer.py      # Synthetic test runner for GET/POST/PUT/DELETE/PATCH/OPTIONS/uploads
├── requirements.txt     # Python dependencies
├── Dockerfile           # Multi-stage Docker build configuration
├── docker-compose.yml   # Docker Compose orchestration
├── entrypoint.sh        # Container startup script
├── Procfile             # Heroku / Railway deployment config
├── render.yaml          # Render.com deployment config
├── uploads/             # Directory for stored multipart file uploads
└── sniffer_logs.db      # SQLite database file (created automatically)
```

---

## 📜 License

MIT License
