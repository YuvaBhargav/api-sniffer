import os
import sys
import time
import json
import uuid
import hashlib
import threading
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, make_response, render_template_string

# Optional Streamlit imports (safe for WSGI servers like PythonAnywhere)
try:
    import streamlit as st
    from streamlit_autorefresh import st_autorefresh
    HAS_STREAMLIT = True
except Exception:
    st = None
    st_autorefresh = None
    HAS_STREAMLIT = False

try:
    import tornado.web
except Exception:
    tornado = None

import db

# -----------------------------------------------------------------------------
# 1. Configuration & Directories
# -----------------------------------------------------------------------------
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

API_PORT = int(os.environ.get("API_PORT", 5000))

MOCK_CONFIG = {
    "status_code": 200,
    "response_body": '{"status": "success", "message": "Request captured successfully"}',
    "response_headers": {"Content-Type": "application/json", "X-Sniffer-Served": "true"},
    "delay_ms": 0
}

# -----------------------------------------------------------------------------
# 2. Flask Webhook Receiver & Dashboard App (PythonAnywhere Native)
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)

# Embedded HTML/JS Web Dashboard Template for PythonAnywhere
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛰️ API Sniffer Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0e1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { background-color: #161b22; border: 1px solid #30363d; color: #c9d1d9; }
        .badge-get { background-color: #2e7d32; }
        .badge-post { background-color: #1565c0; }
        .badge-put { background-color: #f57c00; }
        .badge-delete { background-color: #c62828; }
        .badge-patch { background-color: #6a1b9a; }
        pre { background-color: #0d1117; color: #58a6ff; padding: 10px; border-radius: 6px; border: 1px solid #30363d; font-size: 0.85rem; }
        .accordion-button { background-color: #21262d; color: #c9d1d9; }
        .accordion-button:not(.collapsed) { background-color: #30363d; color: #58a6ff; }
        .accordion-item { background-color: #161b22; border-color: #30363d; }
    </style>
</head>
<body class="p-3">
    <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h2>🛰️ API Request Sniffer Dashboard</h2>
            <div>
                <button class="btn btn-outline-danger btn-sm me-2" onclick="clearLogs()">🗑️ Clear Logs</button>
                <a href="/export/json" class="btn btn-outline-success btn-sm me-1" download>📥 JSON</a>
                <a href="/export/csv" class="btn btn-outline-primary btn-sm" download>📥 CSV</a>
            </div>
        </div>

        <!-- Metrics Row -->
        <div class="row g-2 mb-3">
            <div class="col-md-2"><div class="card p-2 text-center"><h6>Total Requests</h6><h3 id="stat-total">0</h3></div></div>
            <div class="col-md-2"><div class="card p-2 text-center"><h6>🟢 GET</h6><h3 id="stat-get">0</h3></div></div>
            <div class="col-md-2"><div class="card p-2 text-center"><h6>🔵 POST</h6><h3 id="stat-post">0</h3></div></div>
            <div class="col-md-2"><div class="card p-2 text-center"><h6>🟡 PUT</h6><h3 id="stat-put">0</h3></div></div>
            <div class="col-md-2"><div class="card p-2 text-center"><h6>🔴 DELETE</h6><h3 id="stat-delete">0</h3></div></div>
            <div class="col-md-2"><div class="card p-2 text-center"><h6>🟣 PATCH</h6><h3 id="stat-patch">0</h3></div></div>
        </div>

        <div class="row">
            <!-- Left Sidebar: cURL Generator -->
            <div class="col-md-4 mb-3">
                <div class="card p-3">
                    <h4>⚡ cURL Generator</h4>
                    <small class="text-muted mb-2">Generate cURL commands for your laptop terminal</small>
                    
                    <label class="form-label mt-2">Target Host</label>
                    <input type="text" id="gen-host" class="form-control form-control-sm bg-dark text-white border-secondary" value="" placeholder="https://yourname.pythonanywhere.com">
                    
                    <div class="row g-2 mt-1">
                        <div class="col-5">
                            <label class="form-label">Method</label>
                            <select id="gen-method" class="form-select form-select-sm bg-dark text-white border-secondary" onchange="updateCurl()">
                                <option>GET</option><option selected>POST</option><option>PUT</option><option>DELETE</option><option>PATCH</option>
                            </select>
                        </div>
                        <div class="col-7">
                            <label class="form-label">Subpath</label>
                            <input type="text" id="gen-subpath" class="form-control form-control-sm bg-dark text-white border-secondary" value="/api/v1/test" oninput="updateCurl()">
                        </div>
                    </div>

                    <label class="form-label mt-2">Test Way</label>
                    <select id="gen-mode" class="form-select form-select-sm bg-dark text-white border-secondary" onchange="updateCurl()">
                        <option value="payload">1. Data in Payload (Body)</option>
                        <option value="file">2. Data as a File</option>
                        <option value="query">3. Data as Query</option>
                    </select>

                    <div id="mode-payload-div" class="mt-2">
                        <label class="form-label">Payload Data</label>
                        <textarea id="gen-payload" class="form-control form-control-sm bg-dark text-white border-secondary" rows="3" oninput="updateCurl()">{"event": "test", "status": "activepan", "email": "gmail"}</textarea>
                    </div>

                    <div id="mode-file-div" class="mt-2 d-none">
                        <label class="form-label">Laptop File Path</label>
                        <input type="text" id="gen-file" class="form-control form-control-sm bg-dark text-white border-secondary" value="@photo.png" oninput="updateCurl()">
                    </div>

                    <div id="mode-query-div" class="mt-2 d-none">
                        <label class="form-label">Query String</label>
                        <input type="text" id="gen-query" class="form-control form-control-sm bg-dark text-white border-secondary" value="event=test&status=activepan&email=gmail" oninput="updateCurl()">
                    </div>

                    <label class="form-label mt-3">cURL Command Output</label>
                    <pre id="curl-out">curl -X POST ...</pre>
                </div>
            </div>

            <!-- Right Feed: Logged Requests -->
            <div class="col-md-8">
                <div class="card p-3">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h4>📋 Captured Requests Feed</h4>
                        <input type="text" id="search-input" class="form-control form-control-sm w-50 bg-dark text-white border-secondary" placeholder="🔍 Search logs..." oninput="loadLogs()">
                    </div>
                    <div class="accordion" id="logsAccordion">Loading logs...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('gen-host').value = window.location.origin;

        function updateCurl() {
            const host = document.getElementById('gen-host').value.replace(/\\/$/, '');
            const method = document.getElementById('gen-method').value;
            const subpath = document.getElementById('gen-subpath').value;
            const mode = document.getElementById('gen-mode').value;
            
            document.getElementById('mode-payload-div').classList.toggle('d-none', mode !== 'payload');
            document.getElementById('mode-file-div').classList.toggle('d-none', mode !== 'file');
            document.getElementById('mode-query-div').classList.toggle('d-none', mode !== 'query');

            let url = host + subpath;
            let cmd = `curl -X ${method} "${url}"`;

            if (mode === 'payload') {
                const payload = document.getElementById('gen-payload').value;
                cmd += ` \\\n  -H "Content-Type: application/json" \\\n  -d '${payload}'`;
            } else if (mode === 'file') {
                let filepath = document.getElementById('gen-file').value;
                if (!filepath.startsWith('@')) filepath = '@' + filepath;
                cmd += ` \\\n  -F "file=${filepath}"`;
            } else if (mode === 'query') {
                const q = document.getElementById('gen-query').value;
                url += `?${q}`;
                cmd = `curl -X ${method} "${url}"`;
            }

            document.getElementById('curl-out').innerText = cmd;
        }

        async function loadLogs() {
            const res = await fetch('/api/logs_json');
            const logs = await res.json();
            
            document.getElementById('stat-total').innerText = logs.length;
            document.getElementById('stat-get').innerText = logs.filter(l => l.method==='GET').length;
            document.getElementById('stat-post').innerText = logs.filter(l => l.method==='POST').length;
            document.getElementById('stat-put').innerText = logs.filter(l => l.method==='PUT').length;
            document.getElementById('stat-delete').innerText = logs.filter(l => l.method==='DELETE').length;
            document.getElementById('stat-patch').innerText = logs.filter(l => l.method==='PATCH').length;

            const search = document.getElementById('search-input').value.toLowerCase();
            const filtered = logs.filter(l => !search || JSON.stringify(l).toLowerCase().includes(search));

            const container = document.getElementById('logsAccordion');
            if (filtered.length === 0) {
                container.innerHTML = '<div class="alert alert-info">No logged requests yet. Run a cURL command from your terminal to see logs here live!</div>';
                return;
            }

            container.innerHTML = filtered.map((item, idx) => `
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${idx}">
                            <span class="badge badge-${item.method.toLowerCase()} me-2">${item.method}</span>
                            <strong>${item.path}</strong> &nbsp;—&nbsp; <small class="text-muted">${item.timestamp} from ${item.client_ip}</small>
                        </button>
                    </h2>
                    <div id="collapse${idx}" class="accordion-collapse collapse" data-bs-parent="#logsAccordion">
                        <div class="accordion-body">
                            <h6>📊 Metadata</h6>
                            <p class="mb-1"><strong>URL:</strong> <code>${item.url}</code> | <strong>IP:</strong> <code>${item.client_ip}</code> | <strong>User-Agent:</strong> <code>${item.user_agent}</code></p>
                            
                            <h6 class="mt-3">🔍 Query Parameters</h6>
                            <pre>${JSON.stringify(item.query_params, null, 2)}</pre>
                            
                            <h6 class="mt-3">📋 Headers</h6>
                            <pre>${JSON.stringify(item.headers, null, 2)}</pre>
                            
                            <h6 class="mt-3">📝 Body Content</h6>
                            <pre>${item.body || (item.form_data ? JSON.stringify(item.form_data, null, 2) : '<empty>')}</pre>
                            
                            ${item.files && item.files.length ? `<h6 class="mt-3">📁 Uploaded Files</h6><pre>${JSON.stringify(item.files, null, 2)}</pre>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        }

        async function clearLogs() {
            if (confirm("Clear all logs?")) {
                await fetch('/api/clear_logs', { method: 'POST' });
                loadLogs();
            }
        }

        updateCurl();
        loadLogs();
        setInterval(loadLogs, 2000);
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@flask_app.route("/", methods=["GET"])
@flask_app.route("/dashboard", methods=["GET"])
@flask_app.route("/ui", methods=["GET"])
def web_dashboard():
    if request.args and request.path == "/":
        query_params_dict = request.args.to_dict(flat=False)
        query_params_clean = {k: v[0] if len(v) == 1 else v for k, v in query_params_dict.items()}
        raw_qs = request.query_string.decode("utf-8", errors="replace")
        
        req_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        db.insert_log({
            "request_id": req_id,
            "timestamp": timestamp,
            "method": "GET",
            "url": request.url,
            "path": "/",
            "query_params": query_params_clean,
            "raw_query_string": raw_qs,
            "headers": dict(request.headers),
            "cookies": dict(request.cookies),
            "client_ip": request.remote_addr or "127.0.0.1",
            "user_agent": request.headers.get("User-Agent", ""),
            "content_type": "",
            "content_length": 0,
            "body_type": "empty",
            "body": "",
            "form_data": {},
            "files": [],
            "response_status": 200,
            "duration_ms": 0.5
        })

    return render_template_string(DASHBOARD_HTML)

@flask_app.route("/api/logs_json", methods=["GET"])
def get_logs_json():
    return jsonify(db.get_logs(limit=200))

@flask_app.route("/api/clear_logs", methods=["POST"])
def api_clear_logs():
    db.clear_logs()
    return jsonify({"status": "cleared"})

@flask_app.route("/export/json", methods=["GET"])
def export_json():
    response = make_response(db.export_logs_json())
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = "attachment; filename=api_logs.json"
    return response

@flask_app.route("/export/csv", methods=["GET"])
def export_csv():
    response = make_response(db.export_logs_csv())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=api_logs.csv"
    return response

@flask_app.route("/healthz", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "api-sniffer-listener",
        "total_logged": db.get_total_count(),
        "timestamp": datetime.now().isoformat()
    }), 200

@flask_app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@flask_app.route("/webhook/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@flask_app.route("/capture/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@flask_app.route("/hook/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def catch_all(subpath=""):
    start_time = time.time()
    req_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    if MOCK_CONFIG["delay_ms"] > 0:
        time.sleep(MOCK_CONFIG["delay_ms"] / 1000.0)

    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.headers.get("X-Real-IP", "") or
        request.headers.get("CF-Connecting-IP", "") or
        request.remote_addr or
        "127.0.0.1"
    )

    query_params_dict = request.args.to_dict(flat=False)
    query_params_clean = {k: v[0] if len(v) == 1 else v for k, v in query_params_dict.items()}

    raw_query_string = request.query_string.decode("utf-8", errors="replace")
    headers_dict = dict(request.headers)
    cookies_dict = dict(request.cookies)

    form_data_raw = request.form.to_dict(flat=False)
    form_data_clean = {k: v[0] if len(v) == 1 else v for k, v in form_data_raw.items()}

    files_info = []
    for file_key, file_obj in request.files.items():
        if file_obj and file_obj.filename:
            orig_filename = secure_filename(file_obj.filename)
            saved_filename = f"{int(time.time())}_{uuid.uuid4().hex[:6]}_{orig_filename}"
            saved_path = os.path.join(UPLOAD_DIR, saved_filename)
            
            file_obj.save(saved_path)
            file_size = os.path.getsize(saved_path)
            
            md5_hash = hashlib.md5()
            with open(saved_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            
            files_info.append({
                "field": file_key,
                "filename": orig_filename,
                "saved_filename": saved_filename,
                "saved_path": saved_path,
                "size_bytes": file_size,
                "md5": md5_hash.hexdigest(),
                "content_type": file_obj.content_type or "application/octet-stream"
            })

    raw_data = request.get_data()
    content_type = request.headers.get("Content-Type", "")
    content_length = len(raw_data)

    body_text = ""
    body_type = "empty"

    if content_length > 0:
        try:
            body_text = raw_data.decode("utf-8")
            if "application/json" in content_type:
                body_type = "json"
            elif "application/x-www-form-urlencoded" in content_type:
                body_type = "form"
            elif "multipart/form-data" in content_type:
                body_type = "multipart"
            else:
                body_type = "text"
        except UnicodeDecodeError:
            body_text = f"<binary data: {content_length} bytes, hex: {raw_data[:64].hex()}...>"
            body_type = "binary"

    duration_ms = round((time.time() - start_time) * 1000, 2)

    log_item = {
        "request_id": req_id,
        "timestamp": timestamp,
        "method": request.method,
        "url": request.url,
        "path": f"/{subpath}" if subpath else "/",
        "query_params": query_params_clean,
        "raw_query_string": raw_query_string,
        "headers": headers_dict,
        "cookies": cookies_dict,
        "client_ip": client_ip,
        "user_agent": request.headers.get("User-Agent", ""),
        "content_type": content_type,
        "content_length": content_length,
        "body_type": body_type,
        "body": body_text,
        "form_data": form_data_clean,
        "files": files_info,
        "response_status": MOCK_CONFIG["status_code"],
        "duration_ms": duration_ms
    }

    db.insert_log(log_item)

    try:
        resp_body = MOCK_CONFIG["response_body"]
    except Exception:
        resp_body = '{"status": "ok"}'

    response = make_response(resp_body, MOCK_CONFIG["status_code"])
    for h_key, h_val in MOCK_CONFIG["response_headers"].items():
        response.headers[h_key] = h_val
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Sniffer-Captured"] = "true"

    return response

# -----------------------------------------------------------------------------
# 3. Streamlit Local Server Initialization
# -----------------------------------------------------------------------------
if HAS_STREAMLIT and st:
    @st.cache_resource
    def start_listener_server(port: int):
        def run_flask():
            from werkzeug.serving import make_server
            try:
                server = make_server("0.0.0.0", port, flask_app, threaded=True)
                server.serve_forever()
            except Exception:
                pass

        thread = threading.Thread(target=run_flask, daemon=True)
        thread.start()
        return thread

    start_listener_server(API_PORT)

if HAS_STREAMLIT and __name__ == "__main__":
    st.set_page_config(page_title="API Request Sniffer", page_icon="🛰️", layout="wide")
    st.title("🛰️ API Request Sniffer")
