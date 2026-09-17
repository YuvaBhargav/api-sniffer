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

# Global mock response config
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
    query_params_clean = {}
    for k, v in query_params_dict.items():
        query_params_clean[k] = v[0] if len(v) == 1 else v

    raw_query_string = request.query_string.decode("utf-8", errors="replace")
    headers_dict = dict(request.headers)
    cookies_dict = dict(request.cookies)

    form_data_raw = request.form.to_dict(flat=False)
    form_data_clean = {}
    for k, v in form_data_raw.items():
        form_data_clean[k] = v[0] if len(v) == 1 else v

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
# 3. Start Flask Background Thread
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 4. Helper Code Generators
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
# 5. Streamlit App Layout & cURL Command Generator Studio
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="API Request Sniffer & Inspector",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-capture URL query parameters if present on load
if st.query_params:
    qp = dict(st.query_params)
    req_id = str(uuid.uuid4())
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    raw_qs = "&".join([f"{k}={v}" for k, v in qp.items()])
    
    logged_key = f"logged_qp_{raw_qs}"
    if logged_key not in st.session_state:
        st.session_state[logged_key] = True
        db.insert_log({
            "request_id": req_id,
            "timestamp": ts,
            "method": "GET",
            "url": f"https://yuvapi-sniffer.streamlit.app/?{raw_qs}",
            "path": "/",
            "query_params": qp,
            "raw_query_string": raw_qs,
            "headers": {"User-Agent": "StreamlitCloudURL", "Accept": "*/*"},
            "cookies": {},
            "client_ip": "Streamlit Client",
            "user_agent": "Streamlit Cloud URL",
            "content_type": "",
            "content_length": 0,
            "body_type": "empty",
            "body": "",
            "form_data": {},
            "files": [],
            "response_status": 200,
            "duration_ms": 0.5
        })

# Styling
st.markdown("""
<style>
    .metric-card { background-color: #1e222d; border-radius: 8px; padding: 16px; border: 1px solid #2e3440; }
    .stCodeBlock { font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Sidebar: cURL Command Generator Studio
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚡ cURL Command Generator")
    st.caption("Generate copy-paste cURL commands to run from your laptop terminal:")

    # 1. Target URL Config
    target_api_base = st.text_input("Target API Host URL", value="http://localhost:5000", key="gen_host")
    gen_method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], key="gen_method")
    gen_subpath = st.text_input("Endpoint Subpath", value="/api/v1/test", key="gen_subpath")

    # 2. Select 1 of 3 Test Ways
    gen_mode = st.radio(
        "Select Test Mode:",
        ["1. Data in Payload (Body)", "2. Data as a File", "3. Data as Query"],
        key="gen_mode"
    )

    curl_cmd = ""
    clean_target = f"{target_api_base.rstrip('/')}{gen_subpath}"

    if "1. Data in Payload" in gen_mode:
        st.markdown("**📦 Data Payload**")
        default_payload = '{"event": "test", "status": "activepan", "email": "gmail"}'
        gen_payload = st.text_area("JSON / Text Data", value=default_payload, height=90, key="gen_payload")
        
        # Build cURL for Payload
        cmd_parts = [f"curl -X {gen_method} '{clean_target}'"]
        cmd_parts.append("  -H 'Content-Type: application/json'")
        if gen_payload:
            cmd_parts.append(f"  -d '{gen_payload}'")
        curl_cmd = " \\\n".join(cmd_parts)

    elif "2. Data as a File" in gen_mode:
        st.markdown("**📁 File Path on your Laptop**")
        gen_file_path = st.text_input("Local File Path (e.g. @document.pdf)", value="@sample_file.txt", key="gen_filepath")
        
        file_arg = gen_file_path if gen_file_path.startswith("@") else f"@{gen_file_path}"
        
        # Build cURL for File Upload
        cmd_parts = [f"curl -X {gen_method} '{clean_target}'"]
        cmd_parts.append(f"  -F 'file={file_arg}'")
        curl_cmd = " \\\n".join(cmd_parts)

    elif "3. Data as Query" in gen_mode:
        st.markdown("**🔗 Query String**")
        gen_query = st.text_input("Query String", value="event=test&status=activepan&email=gmail", key="gen_query")
        
        full_query_url = f"{clean_target}?{gen_query}" if gen_query else clean_target
        
        # Build cURL for Query
        curl_cmd = f"curl -X {gen_method} '{full_query_url}'"

    # Display Generated cURL with 1-Click Copy
    st.markdown("### 📋 Copy cURL Command")
    st.code(curl_cmd, language="bash")
    st.caption("Copy this command, paste it into CMD/Terminal on your laptop, and press Enter!")

    st.markdown("---")
    st.header("⚙️ Settings & Controls")
    
    refresh_sec = st.selectbox("Auto-Refresh Rate", [1, 2, 5, 10, "Manual / Off"], index=1)
    if isinstance(refresh_sec, int):
        st_autorefresh(interval=refresh_sec * 1000, key="api_sniffer_auto_refresh")

    st.markdown("---")
    st.subheader("🎭 Mock Response Rules")
    mock_status = st.number_input("Response Status Code", min_value=100, max_value=599, value=MOCK_CONFIG["status_code"])
    mock_body = st.text_area("Response Body", value=MOCK_CONFIG["response_body"], height=70)
    
    MOCK_CONFIG["status_code"] = mock_status
    MOCK_CONFIG["response_body"] = mock_body

    st.markdown("---")
    st.subheader("💾 Export & Clear")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 JSON", data=db.export_logs_json(), file_name="api_logs.json", mime="application/json")
    with col2:
        st.download_button("📥 CSV", data=db.export_logs_csv(), file_name="api_logs.csv", mime="text/csv")

    if st.button("🗑️ Clear All Logs", use_container_width=True):
        db.clear_logs()
        st.rerun()

# -----------------------------------------------------------------------------
# Main Header & Dashboard
# -----------------------------------------------------------------------------
st.title("🛰️ API Request Sniffer & Inspection Dashboard")
st.caption("Capturing, logging, and inspecting incoming HTTP requests in real-time.")

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

# Search & Filter Controls
f_col1, f_col2 = st.columns([3, 1])
with f_col1:
    search_term = st.text_input("🔍 Search Logs", placeholder="Search by path, URL, header, body, query, IP...")
with f_col2:
    method_filter = st.multiselect("Filter Methods", ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])

logs = db.get_logs(
    limit=200,
    method_filter=method_filter if method_filter else None,
    search_query=search_term if search_term else None
)

if not logs:
    st.info("ℹ️ No logs captured yet. Generate a cURL command in the sidebar, run it from your laptop terminal, and view the results here live!")
else:
    st.write(f"Showing **{len(logs)}** logged requests (newest first):")
    
    for item in logs:
        log_id = item["id"]
        method = item["method"]
        path = item["path"]
        ts = item["timestamp"]
        ip = item["client_ip"]
        body_type = item["body_type"]
        files = item["files"]
        file_badge = f" 📁 ({len(files)} file{'s' if len(files)>1 else ''})" if files else ""

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

            with tab_params:
                st.markdown("#### 🔗 URL Query Parameters")
                if item["raw_query_string"]:
                    st.caption(f"**Raw Query String:** `{item['raw_query_string']}`")
                if item["query_params"]:
                    st.json(item["query_params"])
                else:
                    st.info("No query parameters in this request.")

            with tab_headers:
                h_c1, h_c2 = st.columns(2)
                with h_c1:
                    st.markdown("#### 📥 Headers")
                    st.json(item["headers"])
                with h_c2:
                    st.markdown("#### 🍪 Cookies")
                    if item["cookies"]:
                        st.json(item["cookies"])
                    else:
                        st.info("No cookies.")

            with tab_body:
                st.markdown(f"#### 📝 Request Body (`Type: {body_type}`)")
                if item["form_data"]:
                    st.json(item["form_data"])
                if item["body"]:
                    if body_type == "json":
                        try:
                            st.json(json.loads(item["body"]))
                        except Exception:
                            st.code(item["body"], language="json")
                    elif body_type == "binary":
                        st.code(item["body"], language="text")
                    else:
                        st.code(item["body"], language="text")
                elif not item["form_data"]:
                    st.info("Request body is empty.")

            with tab_files:
                st.markdown("#### 📁 Uploaded Files")
                if not item["files"]:
                    st.info("No files uploaded.")
                else:
                    for idx, f_item in enumerate(item["files"]):
                        f_c1, f_c2 = st.columns([3, 1])
                        with f_c1:
                            st.write(f"**Filename:** `{f_item['filename']}` | **Size:** `{f_item['size_bytes']} bytes`")
                            st.write(f"**MD5 Checksum:** `{f_item['md5']}`")
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

            with tab_code:
                st.markdown("#### 💻 Code Snippets & Replay")
                lang = st.radio("Language", ["cURL", "Python (requests)", "JavaScript (fetch)"], horizontal=True, key=f"lang_{log_id}")
                if lang == "cURL":
                    st.code(generate_curl(item), language="bash")
                elif lang == "Python (requests)":
                    st.code(generate_python(item), language="python")
                elif lang == "JavaScript (fetch)":
                    st.code(generate_javascript(item), language="javascript")

                st.markdown("---")
                replay_target = st.text_input("Target URL", value=item["url"], key=f"replay_url_{log_id}")
                if st.button("🚀 Resend Request", key=f"btn_replay_{log_id}"):
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
                    except Exception as e:
                        st.error(f"Replay failed: {e}")

            with tab_actions:
                if st.button("❌ Delete Log Entry", key=f"del_{log_id}"):
                    db.delete_log(log_id)
                    st.rerun()
