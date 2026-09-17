import os
import json
import threading
from datetime import datetime
from collections import deque
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# 1. Persistent Shared Storage (Survives Streamlit Script Re-runs)
@st.cache_resource
def get_log_buffer():
    return deque(maxlen=100)

GLOBAL_LOGS = get_log_buffer()

# 2. Flask Application
flask_app = Flask(__name__)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@flask_app.route("/", defaults={"subpath": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@flask_app.route("/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def catch_all(subpath):
    try:
        body_text = request.get_data().decode("utf-8")
    except Exception:
        body_text = f"<binary: {len(request.get_data())} bytes>"

    files_info = []
    for name, f in request.files.items():
        if f.filename:
            safe_name = secure_filename(f.filename)
            path = os.path.join(UPLOAD_DIR, safe_name)
            f.save(path)
            files_info.append({"field": name, "filename": safe_name, "size": os.path.getsize(path)})

    log_item = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": request.method,
        "path": request.full_path,
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "headers": dict(request.headers),
        "args": request.args.to_dict(),
        "body": body_text,
        "files": files_info,
    }
    
    # Store directly in the cached shared buffer
    GLOBAL_LOGS.appendleft(log_item)
    return jsonify({"files": len(files_info), "method": request.method, "status": "received"})

# 3. Start Flask Thread Once
@st.cache_resource
def start_flask_server():
    server_thread = threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False),
        daemon=True
    )
    server_thread.start()
    return server_thread

start_flask_server()

# 4. Streamlit UI
st.set_page_config(page_title="API Sniffer", layout="wide")
st_autorefresh(interval=2000, key="auto_refresh")

st.title("🛰️ In-App API Query Monitor")

col1, col2 = st.columns([1, 4])
with col1:
    st.metric("Logged Requests", len(GLOBAL_LOGS))
    if st.button("Clear Logs"):
        GLOBAL_LOGS.clear()
        st.rerun()

with col2:
    st.caption("Listening on port `5001`. Refresh interval: 2 seconds.")

if not GLOBAL_LOGS:
    st.info("Awaiting incoming requests...")
else:
    for item in list(GLOBAL_LOGS):
        with st.expander(f"[{item['method']}] {item['path']} — {item['time']} ({item['ip']})"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Query Params**")
                st.json(item["args"])
                st.markdown("**Files Uploaded**")
                st.json(item["files"])
                st.markdown("**Headers**")
                st.json(item["headers"])
            with c2:
                st.markdown("**Raw Body**")
                try:
                    st.json(json.loads(item["body"]))
                except Exception:
                    st.code(item["body"] if item["body"] else "<empty>", language="text")