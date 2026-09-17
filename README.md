# 🛰️ Self-Hosted API Request Sniffer & Inspection Engine

A lightweight, high-performance, self-hosted API request sniffer, real-time inspection dashboard, and multi-language query generator built with **Python**, **Flask**, and **SQLite**. Designed to capture, log, inspect, replay, and generate code snippets for incoming HTTP requests across all HTTP methods without hiding or truncating any parameters.

---

## ✨ Key Features

- **Full-Spectrum Request Capture**: Logs `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `HEAD`, and `TRACE` methods across any subpath (`/*`).
- **Complete Parameter Inspection (Un-redacted)**:
  - **Query Parameters**: Full URL query strings and multi-value query array parsing (`?tag=a&tag=b`).
  - **Headers & Cookies**: Complete, un-redacted headers and cookie dictionary view.
  - **Payload & Body**: Automatic formatting for JSON, URL-encoded form data, raw text, and binary hex fallback.
  - **Zero-Disk Multipart File Uploads**: Uploaded files are converted into **Base64 Data URIs** and saved directly in SQLite (`0 bytes` written to server disk storage). Features MD5 checksums, inline image previews, and 1-click download buttons.
  - **IST Timezone Standardization**: All request timestamps are logged natively in Indian Standard Time (`UTC+5:30`).
- **SQLite Persistence Engine**: Thread-safe SQLite engine (`sniffer_logs.db`) ensuring logs persist reliably across server reloads and container restarts.
- **Multi-Language Query & Command Generator**:
  - Dynamically builds ready-to-run queries across **6 Data Modes**:
    1. 📦 **JSON Payload** (`application/json`)
    2. 📝 **Raw Text Body** (`text/plain`)
    3. 📁 **File Upload** (`multipart/form-data`)
    4. 🔗 **Query Parameters** (`?key=value`)
    5. 📄 **Form Data** (`application/x-www-form-urlencoded`)
    6. ⚪ **Empty Request / Headers Only**
  - Exports code snippets in 4 languages:
    - 💻 **cURL Command**
    - 🐍 **Python (`requests`)**
    - 🟨 **JavaScript (`fetch`)**
    - 🔷 **PowerShell (`Invoke-RestMethod`)**
  - **🚀 Send Test Request Action**: Execute generated HTTP requests directly from the dashboard UI using browser `fetch()` and see them captured live in the feed.
  - **📋 Copy Code Action**: 1-click copy generated code snippets to clipboard.
- **Minimalist Zero-Lag UI**: Dark-themed Single Page Application (SPA) with metric distribution counters, filter search bar, live polling, and CSV/JSON data export.
- **Ready for Cloud Deployment**: Tested for **PythonAnywhere WSGI**, Docker, Render, Railway, and Heroku.

---

## 🏗️ Technical Architecture & System Design

```
+------------------------------------+        +----------------------------------------+
|       API Clients & cURL           |        |           Web Dashboard UI             |
|   cURL / Postman / Mobile / Web    |        |       HTML5 / JS SPA / Dark Theme      |
+-----------------+------------------+        +-------------------+--------------------+
                  |                                               |
                  | HTTP/HTTPS                                    | Send Test / Poll
                  v                                               v
+--------------------------------------------------------------------------------------+
|                           Flask WSGI Server (app.py)                                 |
|                   Wildcard Listener / Un-redacted Parser (IST)                       |
+-----------------+-----------------------------------------------+--------------------+
                  |                                               |
                  v Store Logs & Base64 Files                     v Generate Code
+------------------------------------+        +----------------------------------------+
|      SQLite Database (db.py)       |        |        Query Generator Engine          |
|  Thread-Safe Connection Pool & DB  |        |    6 Data Modes: cURL/Py/JS/PS Snippets|
+------------------------------------+        +----------------------------------------+
```

### Request Processing & Zero-Disk Data Flow

```
Client / Dashboard           Flask Listener (app.py)        Base64 Parser            SQLite Pool (db.py)
      |                             |                             |                            |
      |--- 1. HTTP Request -------->|                             |                            |
      |    (GET/POST/Upload)        |--- 2. Parse Headers ------->|                            |
      |                             |       & Base64 Files        |                            |
      |                             |<-- 3. Return Metadata ------|                            |
      |                             |                             |                            |
      |                             |-------------------------------- 4. Insert Record ------->|
      |                             |                                   (IST Timestamp)        |
      |                             |<------------------------------- 5. Return OK ------------|
      |<-- 6. 200 OK + Live Feed ---|                             |                            |
```

---

## 🗄️ Database Schema Specification (`sniffer_logs`)

The SQLite persistence engine stores logs in table `sniffer_logs`:

| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Internal log entry ID |
| `request_id` | `TEXT` | `NOT NULL, UNIQUE` | UUID v4 request identifier |
| `timestamp` | `TEXT` | `NOT NULL` | IST formatted timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `method` | `TEXT` | `NOT NULL` | HTTP method (`GET`, `POST`, `PUT`, `DELETE`, etc.) |
| `url` | `TEXT` | `NOT NULL` | Full request URL including query string |
| `path` | `TEXT` | `NOT NULL` | Request URL path component |
| `query_params` | `TEXT` | `DEFAULT '{}'` | Serialized JSON dictionary of query params |
| `headers` | `TEXT` | `NOT NULL` | Serialized JSON dictionary of HTTP headers |
| `body_type` | `TEXT` | `NOT NULL` | Data type (`payload` / `text` / `file` / `form` / `empty`) |
| `body` | `TEXT` | `DEFAULT ''` | Raw request body or formatted JSON text |
| `files` | `TEXT` | `DEFAULT '[]'` | Base64 Data URIs, MD5 hashes, filename metadata |
| `client_ip` | `TEXT` | `NOT NULL` | Caller IP address |

---

## ⚡ Multi-Language Query Generator Specification

The dashboard sidebar features an interactive query generator supporting 6 data modes and 4 code target environments:

```
Modes:           [1. JSON Payload] [2. Raw Text] [3. File Upload] [4. Query Params] [5. Form Data] [6. Empty]
Environments:    [💻 cURL] [🐍 Python requests] [🟨 JavaScript fetch] [🔷 PowerShell Invoke-RestMethod]
Actions:         [🚀 Send Test Request]  [📋 Copy Code]
```

---

## 🚀 Quickstart & Local Setup

### 1. Local Development Run

```bash
# Clone repository
git clone https://github.com/YuvaBhargav/api-sniffer.git
cd api-sniffer

# Install dependencies
pip install -r requirements.txt

# Start application server
python app.py
```

Open your browser at:
- **Web Dashboard**: `http://127.0.0.1:5000/dashboard`
- **Listener API**: `http://127.0.0.1:5000/api/v1/test`

---

### 2. Run Synthetic Test Suite

While `app.py` is running, execute the synthetic test runner to verify all 7 HTTP method variants and file uploads:

```bash
python test_sniffer.py
```

---

### 3. Docker Deployment

Launch containerized instance with Docker Compose:

```bash
docker-compose up --build -d
```

---

## 🧪 Example cURL Test Commands

```bash
# 1. GET Request with Query Parameters
curl -X GET "http://localhost:5000/api/v1/users?event=test&status=active&email=gmail"

# 2. POST Request with JSON Body
curl -X POST "http://localhost:5000/api/v1/orders" \
  -H "Content-Type: application/json" \
  -d '{"event": "test", "status": "activepan", "email": "gmail"}'

# 3. PUT Request with Raw Text Body
curl -X PUT "http://localhost:5000/api/v1/settings" \
  -H "Content-Type: text/plain" \
  -d "sample text body data"

# 4. Form Data Request
curl -X POST "http://localhost:5000/api/v1/form" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "field1=val1&field2=val2"

# 5. Multipart File Upload
curl -X POST "http://localhost:5000/api/v1/upload" \
  -F "file=@photo.png"
```

---

## 🌐 Deploying to PythonAnywhere

1. In PythonAnywhere Web settings, point your WSGI configuration file (`/var/www/<username>_pythonanywhere_com_wsgi.py`) to:

```python
import sys, os
path = '/home/<username>/api-sniffer/api-sniffer'
if path not in sys.path:
    sys.path.append(path)

from app import flask_app as application
```

2. Pull the repository inside your PythonAnywhere console:
```bash
cd /home/<username>/api-sniffer/api-sniffer
git pull origin main
```
3. Click **Reload** under the Web tab.
4. Access dashboard live at: `https://<username>.pythonanywhere.com/dashboard`

---

## 📁 Repository Structure

```
.
├── app.py               # Main Flask WSGI application, wildcard listener, & Dashboard SPA
├── db.py                # SQLite database connection pool, Base64 URI file encoder, & export
├── api_streamlit.py     # Streamlit entrypoint wrapper
├── test_sniffer.py      # Automated synthetic test runner (7/7 method test cases)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Multi-stage Docker build configuration
├── docker-compose.yml   # Docker Compose orchestration
├── entrypoint.sh        # Container startup script
├── Procfile             # Heroku / Railway deployment config
├── render.yaml          # Render.com deployment config
└── sniffer_logs.db      # SQLite database file (created automatically)
```

---

## 📜 License

MIT License
