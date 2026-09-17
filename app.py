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
# 2. Flask Webhook Receiver & Minimalist Zero-Lag Dashboard App
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)

# Ultra-Fast Minimalist Dark-Mode HTML/JS Dashboard Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛰️ API Sniffer</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: #0b0e14; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 16px; font-size: 14px; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #21262d; padding-bottom: 12px; margin-bottom: 16px; }
        h1 { font-size: 1.25rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .btn { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; }
        .btn:hover { background: #30363d; color: #fff; }
        .btn-danger { background: #7ee787; color: #0b0e14; border: none; font-weight: 600; }
        .btn-danger:hover { background: #56d364; }
        .btn-clear { background: #da3633; color: #fff; border: none; }
        .btn-clear:hover { background: #f85149; }
        
        .metrics-bar { display: flex; gap: 12px; margin-bottom: 16px; }
        .metric-pill { background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 8px 14px; display: flex; align-items: center; gap: 8px; font-size: 12px; }
        .metric-num { font-weight: 700; font-size: 14px; }
        
        .layout-grid { display: grid; grid-template-columns: 360px 1fr; gap: 16px; }
        .panel { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 14px; }
        .panel-title { font-weight: 600; font-size: 13px; margin-bottom: 10px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }

        label { display: block; font-size: 12px; color: #8b949e; margin-top: 8px; margin-bottom: 4px; }
        input, select, textarea { width: 100%; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 6px 10px; border-radius: 6px; font-size: 12px; font-family: inherit; }
        input:focus, select:focus, textarea:focus { border-color: #58a6ff; outline: none; }

        .method-badge { padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
        .badge-GET { background: #238636; color: #fff; }
        .badge-POST { background: #1f6feb; color: #fff; }
        .badge-PUT { background: #d29922; color: #0b0e14; }
        .badge-DELETE { background: #da3633; color: #fff; }
        .badge-PATCH { background: #8957e5; color: #fff; }

        .log-item { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; margin-bottom: 8px; overflow: hidden; }
        .log-header { padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
        .log-header:hover { background: #161b22; }
        .log-title { display: flex; align-items: center; gap: 10px; font-family: monospace; font-size: 13px; }
        .log-meta { color: #8b949e; font-size: 11px; }

        .log-details { display: none; padding: 12px; border-top: 1px solid #21262d; background: #090c10; font-size: 12px; }
        .log-item.open .log-details { display: block; }
        
        pre { background: #161b22; color: #79c0ff; padding: 8px 10px; border-radius: 6px; font-family: monospace; font-size: 11px; overflow-x: auto; border: 1px solid #21262d; margin-top: 4px; margin-bottom: 8px; white-space: pre-wrap; word-break: break-all; }
        .section-sub { font-weight: 600; color: #8b949e; font-size: 11px; text-transform: uppercase; margin-top: 8px; }
    </style>
</head>
<body>
    <header>
        <h1>🛰️ API Request Sniffer</h1>
        <div style="display: flex; gap: 8px;">
            <button class="btn btn-clear" onclick="clearLogs()">🗑️ Clear</button>
            <a href="/export/json" class="btn" download>📥 JSON</a>
            <a href="/export/csv" class="btn" download>📥 CSV</a>
        </div>
    </header>

    <!-- Minimal Metrics -->
    <div class="metrics-bar">
        <div class="metric-pill"><span>Total:</span> <span class="metric-num" id="stat-total">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-GET">GET</span> <span class="metric-num" id="stat-get">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-POST">POST</span> <span class="metric-num" id="stat-post">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-PUT">PUT</span> <span class="metric-num" id="stat-put">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-DELETE">DELETE</span> <span class="metric-num" id="stat-delete">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-PATCH">PATCH</span> <span class="metric-num" id="stat-patch">0</span></div>
    </div>

    <div class="layout-grid">
        <!-- Sidebar: Minimal cURL Builder -->
        <div class="panel">
            <div class="panel-title">⚡ cURL Generator</div>
            
            <label>Target Host</label>
            <input type="text" id="gen-host" value="" oninput="updateCurl()">

            <div style="display: flex; gap: 8px;">
                <div style="flex: 1;">
                    <label>Method</label>
                    <select id="gen-method" onchange="updateCurl()">
                        <option>GET</option><option selected>POST</option><option>PUT</option><option>DELETE</option><option>PATCH</option>
                    </select>
                </div>
                <div style="flex: 2;">
                    <label>Subpath</label>
                    <input type="text" id="gen-subpath" value="/api/v1/test" oninput="updateCurl()">
                </div>
            </div>

            <label>Test Mode</label>
            <select id="gen-mode" onchange="updateCurl()">
                <option value="payload">1. Data in Payload (Body)</option>
                <option value="file">2. Data as a File</option>
                <option value="query">3. Data as Query</option>
            </select>

            <div id="div-payload">
                <label>Payload (JSON / Text)</label>
                <textarea id="gen-payload" rows="3" oninput="updateCurl()">{"event": "test", "status": "activepan", "email": "gmail"}</textarea>
            </div>

            <div id="div-file" style="display: none;">
                <label>Laptop File Path</label>
                <input type="text" id="gen-file" value="@photo.png" oninput="updateCurl()">
            </div>

            <div id="div-query" style="display: none;">
                <label>Query String</label>
                <input type="text" id="gen-query" value="event=test&status=activepan&email=gmail" oninput="updateCurl()">
            </div>

            <label style="margin-top: 12px;">cURL Command</label>
            <pre id="curl-out">curl ...</pre>
        </div>

        <!-- Main Feed -->
        <div class="panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div class="panel-title" style="margin-bottom: 0;">📋 Captured Feed</div>
                <input type="text" id="search-input" style="width: 220px;" placeholder="🔍 Filter logs..." oninput="filterLogs()">
            </div>
            <div id="logs-container">No requests logged yet.</div>
        </div>
    </div>

    <script>
        let cachedLogs = [];
        let lastLogHash = "";
        document.getElementById('gen-host').value = window.location.origin;

        function updateCurl() {
            const host = document.getElementById('gen-host').value.replace(/\/$/, '');
            const method = document.getElementById('gen-method').value;
            const subpath = document.getElementById('gen-subpath').value;
            const mode = document.getElementById('gen-mode').value;
            
            document.getElementById('div-payload').style.display = mode === 'payload' ? 'block' : 'none';
            document.getElementById('div-file').style.display = mode === 'file' ? 'block' : 'none';
            document.getElementById('div-query').style.display = mode === 'query' ? 'block' : 'none';

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

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs_json');
                const logs = await res.json();
                
                const currentHash = JSON.stringify(logs);
                if (currentHash === lastLogHash) return; // Zero-lag: skip DOM re-render if data unchanged
                lastLogHash = currentHash;
                cachedLogs = logs;

                // Update Metrics
                document.getElementById('stat-total').innerText = logs.length;
                document.getElementById('stat-get').innerText = logs.filter(l => l.method==='GET').length;
                document.getElementById('stat-post').innerText = logs.filter(l => l.method==='POST').length;
                document.getElementById('stat-put').innerText = logs.filter(l => l.method==='PUT').length;
                document.getElementById('stat-delete').innerText = logs.filter(l => l.method==='DELETE').length;
                document.getElementById('stat-patch').innerText = logs.filter(l => l.method==='PATCH').length;

                filterLogs();
            } catch (e) {}
        }

        function filterLogs() {
            const query = document.getElementById('search-input').value.toLowerCase();
            const container = document.getElementById('logs-container');
            const filtered = cachedLogs.filter(l => !query || JSON.stringify(l).toLowerCase().includes(query));

            if (filtered.length === 0) {
                container.innerHTML = '<div style="color: #8b949e; padding: 20px; text-align: center;">No requests captured yet.</div>';
                return;
            }

            container.innerHTML = filtered.map((item, idx) => `
                <div class="log-item" id="item-${idx}">
                    <div class="log-header" onclick="document.getElementById('item-${idx}').classList.toggle('open')">
                        <div class="log-title">
                            <span class="method-badge badge-${item.method}">${item.method}</span>
                            <span>${escapeHtml(item.path)}</span>
                        </div>
                        <div class="log-meta">${item.timestamp} | ${item.client_ip}</div>
                    </div>
                    <div class="log-details">
                        <div class="section-sub">Query Params</div>
                        <pre>${JSON.stringify(item.query_params, null, 2)}</pre>
                        
                        <div class="section-sub">Headers</div>
                        <pre>${JSON.stringify(item.headers, null, 2)}</pre>
                        
                        <div class="section-sub">Body</div>
                        <pre>${escapeHtml(item.body || (item.form_data ? JSON.stringify(item.form_data, null, 2) : '<empty>'))}</pre>

                        ${item.files && item.files.length ? `<div class="section-sub">Files</div><pre>${JSON.stringify(item.files, null, 2)}</pre>` : ''}
                    </div>
                </div>
            `).join('');
        }

        function escapeHtml(str) {
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        async function clearLogs() {
            if (confirm("Clear all logs?")) {
                await fetch('/api/clear_logs', { method: 'POST' });
                lastLogHash = "";
                fetchLogs();
            }
        }

        updateCurl();
        fetchLogs();
        setInterval(fetchLogs, 2000);
    </script>
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
