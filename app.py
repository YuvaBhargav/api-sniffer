import os
import sys
import time
import json
import uuid
import hashlib
import threading
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, make_response

import streamlit as st
from streamlit_autorefresh import st_autorefresh

import db

# -----------------------------------------------------------------------------
# 1. Configuration & Directories
# -----------------------------------------------------------------------------
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

API_PORT = int(os.environ.get("API_PORT", 5000))

# Thread-safe global mock config
MOCK_CONFIG = {
    "status_code": 200,
    "response_body": '{"status": "success", "message": "Request captured successfully"}',
    "response_headers": {"Content-Type": "application/json", "X-Sniffer-Served": "true"},
    "delay_ms": 0
}

# -----------------------------------------------------------------------------
# 2. Flask Webhook Receiver Application
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route("/healthz", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "api-sniffer-listener",
        "total_logged": db.get_total_count(),
        "timestamp": datetime.now().isoformat()
    }), 200

@flask_app.route("/", defaults={"subpath": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@flask_app.route("/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def catch_all(subpath):
    start_time = time.time()
    req_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    # Artificial latency delay if configured
    if MOCK_CONFIG["delay_ms"] > 0:
        time.sleep(MOCK_CONFIG["delay_ms"] / 1000.0)

    # 1. Extract IP address accurately
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.headers.get("X-Real-IP", "") or
        request.headers.get("CF-Connecting-IP", "") or
        request.remote_addr or
        "127.0.0.1"
    )

    # 2. Extract Query Parameters (Full, un-redacted, handling multi-value arrays)
    query_params_dict = request.args.to_dict(flat=False)
    # Simplify single-item lists for cleaner representation while retaining lists for multi-value
    query_params_clean = {}
    for k, v in query_params_dict.items():
        query_params_clean[k] = v[0] if len(v) == 1 else v

    raw_query_string = request.query_string.decode("utf-8", errors="replace")

    # 3. Extract Headers & Cookies (Un-redacted)
    headers_dict = dict(request.headers)
    cookies_dict = dict(request.cookies)

    # 4. Extract Form Data (Un-redacted)
    form_data_raw = request.form.to_dict(flat=False)
    form_data_clean = {}
    for k, v in form_data_raw.items():
        form_data_clean[k] = v[0] if len(v) == 1 else v

    # 5. Extract Files (Multipart upload handling)
    files_info = []
    for file_key, file_obj in request.files.items():
        if file_obj and file_obj.filename:
            orig_filename = secure_filename(file_obj.filename)
            saved_filename = f"{int(time.time())}_{uuid.uuid4().hex[:6]}_{orig_filename}"
            saved_path = os.path.join(UPLOAD_DIR, saved_filename)
            
            # Save file
            file_obj.save(saved_path)
            file_size = os.path.getsize(saved_path)
            
            # Compute MD5 checksum
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

    # 6. Extract Raw Body & Determine Body Type
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

    # 7. Prepare log item & persist to SQLite
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

    # 8. Build custom HTTP response based on user configuration
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
# 3. Start Flask Background Thread
# -----------------------------------------------------------------------------
@st.cache_resource
def start_listener_server(port: int):
    def run_flask():
        from werkzeug.serving import make_server
        server = make_server("0.0.0.0", port, flask_app, threaded=True)
        server.serve_forever()

    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    return thread

start_listener_server(API_PORT)

# -----------------------------------------------------------------------------
# 4. Helper Functions for Code Generators
# -----------------------------------------------------------------------------
def generate_curl(item: dict) -> str:
    url = item['url']
    method = item['method']
    headers = item['headers']
    body = item['body']
    
    cmd = [f"curl -X {method} '{url}'"]
    for k, v in headers.items():
        if k.lower() not in ["host", "content-length"]:
            cmd.append(f"  -H '{k}: {v}'")
    if body and method in ["POST", "PUT", "PATCH", "DELETE"]:
        escaped_body = body.replace("'", "'\\''")
        cmd.append(f"  --data-raw '{escaped_body}'")
    return " \\\n".join(cmd)

def generate_python(item: dict) -> str:
    url = item['url']
    method = item['method'].lower()
    headers = item['headers']
    body = item['body']
    
    code = ["import requests\n"]
    code.append(f"url = '{url}'")
    code.append(f"headers = {json.dumps(headers, indent=2)}")
    if item['body_type'] == 'json' and body:
        try:
            parsed = json.loads(body)
            code.append(f"json_payload = {json.dumps(parsed, indent=2)}")
            code.append(f"response = requests.{method}(url, headers=headers, json=json_payload)")
        except Exception:
            code.append(f"data = {json.dumps(body)}")
            code.append(f"response = requests.{method}(url, headers=headers, data=data)")
    elif body:
        code.append(f"data = {json.dumps(body)}")
        code.append(f"response = requests.{method}(url, headers=headers, data=data)")
    else:
        code.append(f"response = requests.{method}(url, headers=headers)")
    
    code.append("print(response.status_code)")
    code.append("print(response.text)")
    return "\n".join(code)

def generate_javascript(item: dict) -> str:
    url = item['url']
    method = item['method']
    headers = item['headers']
    body = item['body']
    
    options = {"method": method, "headers": headers}
    if body and method in ["POST", "PUT", "PATCH"]:
        options["body"] = body

    return f"""fetch('{url}', {json.dumps(options, indent=2)})
  .then(response => response.text())
  .then(result => console.log(result))
  .catch(error => console.error('error', error));"""

# -----------------------------------------------------------------------------
# 5. Streamlit Interactive Dashboard UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="API Request Sniffer & Inspector",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished aesthetics
st.markdown("""
<style>
    .metric-card {
        background-color: #1e222d;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #2e3440;
    }
    .badge-get { background-color: #2e7d32; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .badge-post { background-color: #1565c0; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .badge-put { background-color: #f57c00; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .badge-delete { background-color: #c62828; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .badge-patch { background-color: #6a1b9a; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .badge-options { background-color: #424242; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .badge-head { background-color: #37474f; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .stCodeBlock { font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Sidebar Settings & Config
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Sniffer Control & Settings")
    
    st.success(f"🟢 **Listener Active** on Port `{API_PORT}`")
    st.caption("Listening for all `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `HEAD` HTTP requests.")

    st.markdown("---")
    st.subheader("🔄 Live Feed Refresh")
    refresh_sec = st.selectbox("Auto-Refresh Rate", [1, 2, 5, 10, "Manual / Off"], index=1)
    if isinstance(refresh_sec, int):
        st_autorefresh(interval=refresh_sec * 1000, key="api_sniffer_auto_refresh")

    st.markdown("---")
    st.subheader("🎭 Mock Response Rules")
    mock_status = st.number_input("Response HTTP Status Code", min_value=100, max_value=599, value=MOCK_CONFIG["status_code"])
    mock_body = st.text_area("Response Body (JSON/Text)", value=MOCK_CONFIG["response_body"], height=100)
    mock_delay = st.slider("Artificial Latency (ms)", min_value=0, max_value=3000, value=MOCK_CONFIG["delay_ms"], step=100)

    MOCK_CONFIG["status_code"] = mock_status
    MOCK_CONFIG["response_body"] = mock_body
    MOCK_CONFIG["delay_ms"] = mock_delay

    st.markdown("---")
    st.subheader("💾 Data Export & Storage")
    
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        st.download_button(
            "📥 JSON",
            data=db.export_logs_json(),
            file_name=f"api_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    with col_exp2:
        st.download_button(
            "📥 CSV",
            data=db.export_logs_csv(),
            file_name=f"api_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    if st.button("🗑️ Clear All Logs", type="primary", use_container_width=True):
        db.clear_logs()
        st.rerun()

    st.markdown("---")
    st.subheader("🧪 Built-in API Request Tester")
    with st.expander("Send Test Request"):
        test_method = st.selectbox("Method", ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        test_subpath = st.text_input("Subpath", value="/test/webhook")
        test_query = st.text_input("Query String", value="user=john&action=test&tag=demo1&tag=demo2")
        test_body = st.text_area("JSON / Body", value='{"event": "user_signup", "user_id": 1042}')
        
        if st.button("🚀 Send Request Now"):
            import requests as req_lib
            target_url = f"http://127.0.0.1:{API_PORT}{test_subpath}?{test_query}" if test_query else f"http://127.0.0.1:{API_PORT}{test_subpath}"
            try:
                headers = {"Content-Type": "application/json", "User-Agent": "StreamlitSnifferTester/1.0"}
                if test_method in ["POST", "PUT", "PATCH"]:
                    resp = req_lib.request(test_method, target_url, data=test_body, headers=headers, timeout=5)
                else:
                    resp = req_lib.request(test_method, target_url, headers=headers, timeout=5)
                st.success(f"Status Code: {resp.status_code}")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to send request: {e}")

# -----------------------------------------------------------------------------
# Main Header & Dashboard Stats
# -----------------------------------------------------------------------------
st.title("🛰️ API Request Sniffer & Inspection Dashboard")
st.caption(f"Capturing, logging, and displaying incoming HTTP requests in real-time. Listener endpoint: `http://localhost:{API_PORT}/`")

total_logs = db.get_total_count()
method_stats = db.get_method_stats()

m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
m_col1.metric("Total Requests", total_logs)
m_col2.metric("🟢 GET", method_stats.get("GET", 0))
m_col3.metric("🔵 POST", method_stats.get("POST", 0))
m_col4.metric("🟡 PUT", method_stats.get("PUT", 0))
m_col5.metric("🔴 DELETE", method_stats.get("DELETE", 0))
m_col6.metric("🟣 PATCH", method_stats.get("PATCH", 0))

st.markdown("---")

# -----------------------------------------------------------------------------
# Search & Filter Controls
# -----------------------------------------------------------------------------
f_col1, f_col2 = st.columns([3, 1])

with f_col1:
    search_term = st.text_input("🔍 Search Logs (Path, URL, Headers, Body, Params, Client IP)", placeholder="Type path, parameter, header value or keyword...")

with f_col2:
    method_filter = st.multiselect("Filter HTTP Methods", ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])

# Fetch filtered logs from SQLite
logs = db.get_logs(
    limit=200,
    method_filter=method_filter if method_filter else None,
    search_query=search_term if search_term else None
)

if not logs:
    st.info("ℹ️ No incoming HTTP requests logged yet. Send a GET, POST, PUT, DELETE request to `http://localhost:5000/your-path?key=value` to get started!")
else:
    st.write(f"Showing **{len(logs)}** logged requests (sorted newest first):")
    
    for item in logs:
        log_id = item["id"]
        method = item["method"]
        path = item["path"]
        ts = item["timestamp"]
        ip = item["client_ip"]
        body_type = item["body_type"]
        files = item["files"]
        file_badge = f" 📁 ({len(files)} file{'s' if len(files)>1 else ''})" if files else ""

        # Method badge styling
        badge_emoji = {
            "GET": "🟢", "POST": "🔵", "PUT": "🟡",
            "DELETE": "🔴", "PATCH": "🟣", "OPTIONS": "⚪", "HEAD": "⚫"
        }.get(method, "⚪")

        expander_title = f"{badge_emoji} [{method}] {path} — {ts} from {ip}{file_badge}"
        
        with st.expander(expander_title):
            tab_overview, tab_params, tab_headers, tab_body, tab_files, tab_code, tab_actions = st.tabs([
                "📊 Overview",
                "🔍 Query Params",
                "📋 Headers & Cookies",
                "📝 Request Body",
                "📁 Files Uploaded",
                "💻 Code Snippets & Replay",
                "⚙️ Actions"
            ])

            # -----------------------------------------------------------------
            # Tab 1: Overview
            # -----------------------------------------------------------------
            with tab_overview:
                o_c1, o_c2 = st.columns(2)
                with o_c1:
                    st.write(f"**Request ID:** `{item['request_id']}`")
                    st.write(f"**Timestamp:** `{item['timestamp']}`")
                    st.write(f"**Method:** `{item['method']}`")
                    st.write(f"**Full URL:** `{item['url']}`")
                    st.write(f"**Subpath:** `{item['path']}`")
                with o_c2:
                    st.write(f"**Client IP:** `{item['client_ip']}`")
                    st.write(f"**User-Agent:** `{item['user_agent']}`")
                    st.write(f"**Content-Type:** `{item['content_type'] or '<none>'}`")
                    st.write(f"**Payload Size:** `{item['content_length']} bytes`")
                    st.write(f"**Response Status Served:** `{item['response_status']}` ({item['duration_ms']} ms)")

            # -----------------------------------------------------------------
            # Tab 2: Query Parameters (Un-redacted)
            # -----------------------------------------------------------------
            with tab_params:
                st.markdown("#### 🔗 URL Query Parameters (Full & Un-redacted)")
                if item["raw_query_string"]:
                    st.caption(f"**Raw Query String:** `{item['raw_query_string']}`")
                
                if item["query_params"]:
                    st.json(item["query_params"])
                else:
                    st.info("No query parameters present in this request.")

            # -----------------------------------------------------------------
            # Tab 3: Headers & Cookies (Un-redacted)
            # -----------------------------------------------------------------
            with tab_headers:
                h_c1, h_c2 = st.columns(2)
                with h_c1:
                    st.markdown("#### 📥 Request Headers")
                    st.json(item["headers"])
                with h_c2:
                    st.markdown("#### 🍪 Cookies")
                    if item["cookies"]:
                        st.json(item["cookies"])
                    else:
                        st.info("No cookies sent with this request.")

            # -----------------------------------------------------------------
            # Tab 4: Request Body & Form Data (Un-redacted)
            # -----------------------------------------------------------------
            with tab_body:
                st.markdown(f"#### 📝 Request Body (`Type: {body_type}`)")
                
                if item["form_data"]:
                    st.markdown("**Form Data Fields:**")
                    st.json(item["form_data"])

                if item["body"]:
                    if body_type == "json":
                        try:
                            st.json(json.loads(item["body"]))
                        except Exception:
                            st.code(item["body"], language="json")
                    elif body_type == "binary":
                        st.warning("Binary body content detected.")
                        st.code(item["body"], language="text")
                    else:
                        st.code(item["body"], language="text")
                elif not item["form_data"]:
                    st.info("Request body is empty.")

            # -----------------------------------------------------------------
            # Tab 5: Multipart Uploaded Files
            # -----------------------------------------------------------------
            with tab_files:
                st.markdown("#### 📁 Uploaded Files")
                if not item["files"]:
                    st.info("No files uploaded with this request.")
                else:
                    for idx, f_item in enumerate(item["files"]):
                        f_c1, f_c2 = st.columns([3, 1])
                        with f_c1:
                            st.write(f"**Field Name:** `{f_item['field']}`")
                            st.write(f"**Original Filename:** `{f_item['filename']}`")
                            st.write(f"**Size:** `{f_item['size_bytes']} bytes` | **MD5 Checksum:** `{f_item['md5']}`")
                            st.write(f"**MIME Type:** `{f_item['content_type']}`")
                            
                            # Image preview if image file exists
                            if os.path.exists(f_item["saved_path"]) and f_item["content_type"].startswith("image/"):
                                st.image(f_item["saved_path"], width=200, caption=f_item["filename"])
                        
                        with f_c2:
                            if os.path.exists(f_item["saved_path"]):
                                with open(f_item["saved_path"], "rb") as file_data:
                                    st.download_button(
                                        f"📥 Download {f_item['filename']}",
                                        data=file_data,
                                        file_name=f_item['filename'],
                                        mime=f_item['content_type'],
                                        key=f"dl_{log_id}_{idx}"
                                    )

            # -----------------------------------------------------------------
            # Tab 6: Code Snippets & Replay
            # -----------------------------------------------------------------
            with tab_code:
                st.markdown("#### 💻 Export / Copy Request as Code")
                lang = st.radio("Select Language", ["cURL", "Python (requests)", "JavaScript (fetch)"], horizontal=True, key=f"lang_{log_id}")
                
                if lang == "cURL":
                    st.code(generate_curl(item), language="bash")
                elif lang == "Python (requests)":
                    st.code(generate_python(item), language="python")
                elif lang == "JavaScript (fetch)":
                    st.code(generate_javascript(item), language="javascript")

                st.markdown("---")
                st.markdown("#### 🔄 Replay / Resend Request")
                replay_target = st.text_input("Target URL for Replay", value=item["url"], key=f"replay_url_{log_id}")
                
                if st.button("🚀 Resend Captured Request", key=f"btn_replay_{log_id}"):
                    import requests as req_lib
                    try:
                        headers_to_send = {k: v for k, v in item["headers"].items() if k.lower() not in ["host", "content-length"]}
                        res = req_lib.request(
                            method=item["method"],
                            url=replay_target,
                            headers=headers_to_send,
                            data=item["body"] if item["body"] else None,
                            timeout=10
                        )
                        st.success(f"Replay Sent! Response Status: {res.status_code}")
                        st.code(res.text[:1000], language="text")
                    except Exception as e:
                        st.error(f"Replay failed: {e}")

            # -----------------------------------------------------------------
            # Tab 7: Actions
            # -----------------------------------------------------------------
            with tab_actions:
                st.markdown("#### ⚙️ Manage Single Log Entry")
                if st.button("❌ Delete This Log Entry", key=f"del_{log_id}", type="secondary"):
                    db.delete_log(log_id)
                    st.rerun()
