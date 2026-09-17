import os
import sys
import time
import json
import uuid
import hashlib
import base64
import threading
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, make_response, render_template_string

# Timezone definition for IST (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " IST"

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
# 1. Configuration & Setup (Zero Local Disk File Storage Mode)
# -----------------------------------------------------------------------------
API_PORT = int(os.environ.get("API_PORT", 5000))

MOCK_CONFIG = {
    "status_code": 200,
    "response_body": '{"status": "success", "message": "Request captured successfully"}',
    "response_headers": {"Content-Type": "application/json", "X-Sniffer-Served": "true"},
    "delay_ms": 0
}

# -----------------------------------------------------------------------------
# 2. Flask Webhook Receiver & Dashboard App
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
        .btn-clear { background: #da3633; color: #fff; border: none; }
        .btn-clear:hover { background: #f85149; }
        
        .metrics-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
        .metric-pill { background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 6px 12px; display: flex; align-items: center; gap: 6px; font-size: 11px; }
        .metric-num { font-weight: 700; font-size: 13px; }
        
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
        .badge-OPTIONS { background: #6e7681; color: #fff; }
        .badge-HEAD { background: #388bfd; color: #fff; }
        .badge-TRACE { background: #d4a72c; color: #0b0e14; }
        .badge-OTHER { background: #8b949e; color: #0b0e14; }

        .data-badge { padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 11px; margin-left: 8px; display: inline-flex; align-items: center; gap: 4px; }
        .badge-file-type { background: rgba(31, 111, 235, 0.2); color: #58a6ff; border: 1px solid rgba(56, 139, 253, 0.4); }
        .badge-payload-type { background: rgba(137, 87, 229, 0.2); color: #bc8cff; border: 1px solid rgba(163, 113, 247, 0.4); }
        .badge-text-type { background: rgba(210, 153, 34, 0.2); color: #e3b341; border: 1px solid rgba(210, 153, 34, 0.4); }
        .badge-query-type { background: rgba(35, 134, 54, 0.2); color: #56d364; border: 1px solid rgba(46, 160, 67, 0.4); }
        .badge-form-type { background: rgba(210, 153, 34, 0.2); color: #e3b341; border: 1px solid rgba(210, 153, 34, 0.4); }
        .badge-empty-type { background: rgba(110, 118, 129, 0.15); color: #8b949e; border: 1px solid rgba(110, 118, 129, 0.3); }

        .log-item { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; margin-bottom: 8px; overflow: hidden; }
        .log-header { padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
        .log-header:hover { background: #161b22; }
        .log-title { display: flex; align-items: center; gap: 8px; font-family: monospace; font-size: 13px; }
        .log-meta { color: #8b949e; font-size: 11px; }

        .log-details { display: none; padding: 12px; border-top: 1px solid #21262d; background: #090c10; font-size: 12px; }
        .log-item.open .log-details { display: block; }
        
        pre { background: #161b22; color: #79c0ff; padding: 8px 10px; border-radius: 6px; font-family: monospace; font-size: 11px; overflow-x: auto; border: 1px solid #21262d; margin-top: 4px; margin-bottom: 8px; white-space: pre-wrap; word-break: break-all; }
        .section-sub { font-weight: 600; color: #8b949e; font-size: 11px; text-transform: uppercase; margin-top: 8px; }
        
        .file-box { background: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 6px; margin-top: 6px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
        .img-preview { max-width: 100%; max-height: 180px; border-radius: 6px; border: 1px solid #30363d; margin-top: 6px; display: block; }

        /* Responsive Multi-Device Styles */
        @media (max-width: 768px) {
            body { padding: 10px; font-size: 13px; }
            header { flex-direction: column; align-items: flex-start; gap: 10px; }
            header > div { width: 100%; justify-content: flex-start; flex-wrap: wrap; }
            .layout-grid { grid-template-columns: 1fr; gap: 12px; }
            .log-header { flex-direction: column; align-items: flex-start; gap: 6px; }
            .log-title { flex-wrap: wrap; }
            .log-meta { font-size: 10px; }
            .data-badge { margin-left: 0; margin-top: 2px; }
            #search-input { width: 100% !important; margin-top: 8px; }
        }

        @media (max-width: 480px) {
            h1 { font-size: 1.1rem; }
            .metric-pill { font-size: 10px; padding: 4px 8px; }
            .btn { font-size: 11px; padding: 5px 10px; }
        }
    </style>
</head>
<body>
    <header>
        <h1>🛰️ API Request Sniffer <span style="font-size: 11px; color: #58a6ff; font-weight: normal;">(IST Timezone)</span></h1>
        <div style="display: flex; gap: 8px;">
            <button class="btn btn-clear" onclick="clearLogs()">🗑️ Clear</button>
            <a href="/export/json" class="btn" download>📥 JSON</a>
            <a href="/export/csv" class="btn" download>📥 CSV</a>
        </div>
    </header>

    <div class="metrics-bar">
        <div class="metric-pill"><span>Total:</span> <span class="metric-num" id="stat-total">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-GET">GET</span> <span class="metric-num" id="stat-get">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-POST">POST</span> <span class="metric-num" id="stat-post">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-PUT">PUT</span> <span class="metric-num" id="stat-put">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-DELETE">DELETE</span> <span class="metric-num" id="stat-delete">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-PATCH">PATCH</span> <span class="metric-num" id="stat-patch">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-OPTIONS">OPTIONS</span> <span class="metric-num" id="stat-options">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-HEAD">HEAD</span> <span class="metric-num" id="stat-head">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-TRACE">TRACE</span> <span class="metric-num" id="stat-trace">0</span></div>
        <div class="metric-pill"><span class="method-badge badge-OTHER">OTHER</span> <span class="metric-num" id="stat-other">0</span></div>
    </div>

    <div class="layout-grid">
        <!-- Sidebar: Full Query / Command Generator -->
        <div class="panel">
            <div class="panel-title">⚡ Query & Command Generator</div>
            
            <label>Target Host</label>
            <input type="text" id="gen-host" value="" oninput="updateCurl()">

            <div style="display: flex; gap: 8px;">
                <div style="flex: 1;">
                    <label>Method</label>
                    <select id="gen-method" onchange="updateCurl()">
                        <option>GET</option>
                        <option selected>POST</option>
                        <option>PUT</option>
                        <option>DELETE</option>
                        <option>PATCH</option>
                        <option>OPTIONS</option>
                        <option>HEAD</option>
                    </select>
                </div>
                <div style="flex: 2;">
                    <label>Subpath</label>
                    <input type="text" id="gen-subpath" value="/api/v1/test" oninput="updateCurl()">
                </div>
            </div>

            <label>Data Mode (Identifier Type)</label>
            <select id="gen-mode" onchange="updateCurl()">
                <option value="payload">📦 1. JSON Payload</option>
                <option value="text">📝 2. Raw Text Body</option>
                <option value="file">📁 3. File Upload (-F "file=@path")</option>
                <option value="file_content">📄 4. File Content Body (-d "@file.txt")</option>
                <option value="query">🔗 5. Query Parameters</option>
                <option value="form">📄 6. Form Data</option>
                <option value="empty">⚪ 7. Empty Request</option>
            </select>

            <div id="div-payload">
                <label>JSON Payload</label>
                <textarea id="gen-payload" rows="3" oninput="updateCurl()">{"event": "test", "status": "activepan", "email": "gmail"}</textarea>
            </div>

            <div id="div-text" style="display: none;">
                <label>Raw Text Body</label>
                <textarea id="gen-text" rows="3" oninput="updateCurl()">sample text body data</textarea>
            </div>

            <div id="div-file" style="display: none;">
                <label>Laptop File Path</label>
                <input type="text" id="gen-file" value="@photo.png" oninput="updateCurl()">
            </div>

            <div id="div-file-content" style="display: none;">
                <label>File Path to Send Raw Content</label>
                <input type="text" id="gen-file-content" value="@data.txt" oninput="updateCurl()">
            </div>

            <div id="div-query" style="display: none;">
                <label>Query String</label>
                <input type="text" id="gen-query" value="event=test&status=activepan&email=gmail" oninput="updateCurl()">
            </div>

            <div id="div-form" style="display: none;">
                <label>Form Data String</label>
                <input type="text" id="gen-form" value="field1=val1&field2=val2" oninput="updateCurl()">
            </div>

            <label>Code Generator Format</label>
            <select id="gen-lang" onchange="updateCurl()">
                <option value="curl">💻 cURL Command</option>
                <option value="python">🐍 Python (requests)</option>
                <option value="js">🟨 JavaScript (fetch)</option>
                <option value="powershell">🔷 PowerShell (Invoke-RestMethod)</option>
            </select>

            <label style="margin-top: 10px;">Generated Snippet</label>
            <pre id="curl-out">curl ...</pre>

            <div style="display: flex; gap: 8px; margin-top: 8px;">
                <button class="btn" style="flex: 1; background: #1f6feb; color: #fff; border: none; justify-content: center;" id="btn-send" onclick="sendTestRequest()">🚀 Send Test Request</button>
                <button class="btn" style="flex: 1; justify-content: center;" id="btn-copy" onclick="copyGeneratedCode()">📋 Copy Code</button>
            </div>
        </div>

        <!-- Main Feed -->
        <div class="panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div class="panel-title" style="margin-bottom: 0;">📋 Captured Feed (IST)</div>
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
            const host = document.getElementById('gen-host').value.replace(new RegExp('/$'), '');
            const method = document.getElementById('gen-method').value;
            const subpath = document.getElementById('gen-subpath').value;
            const mode = document.getElementById('gen-mode').value;
            const lang = document.getElementById('gen-lang').value;
            
            document.getElementById('div-payload').style.display = mode === 'payload' ? 'block' : 'none';
            document.getElementById('div-text').style.display = mode === 'text' ? 'block' : 'none';
            document.getElementById('div-file').style.display = mode === 'file' ? 'block' : 'none';
            document.getElementById('div-file-content').style.display = mode === 'file_content' ? 'block' : 'none';
            document.getElementById('div-query').style.display = mode === 'query' ? 'block' : 'none';
            document.getElementById('div-form').style.display = mode === 'form' ? 'block' : 'none';

            let url = host + subpath;
            let code = '';

            if (lang === 'curl') {
                let cmd = `curl -X ${method} "${url}"`;
                if (method === 'HEAD') {
                    cmd = `curl -I "${url}"`;
                } else if (mode === 'payload') {
                    const payload = document.getElementById('gen-payload').value;
                    cmd += ` \\\n  -H "Content-Type: application/json" \\\n  -d '${payload}'`;
                } else if (mode === 'text') {
                    const txt = document.getElementById('gen-text').value;
                    cmd += ` \\\n  -H "Content-Type: text/plain" \\\n  -d '${txt}'`;
                } else if (mode === 'file') {
                    let filepath = document.getElementById('gen-file').value;
                    if (!filepath.startsWith('@')) filepath = '@' + filepath;
                    cmd += ` \\\n  -F "file=${filepath}"`;
                } else if (mode === 'file_content') {
                    let filepath = document.getElementById('gen-file-content').value;
                    if (!filepath.startsWith('@')) filepath = '@' + filepath;
                    cmd += ` \\\n  -H "Content-Type: text/plain" \\\n  -d "${filepath}"`;
                } else if (mode === 'query') {
                    const q = document.getElementById('gen-query').value;
                    url += `?${q}`;
                    cmd = method === 'HEAD' ? `curl -I "${url}"` : `curl -X ${method} "${url}"`;
                } else if (mode === 'form') {
                    const form = document.getElementById('gen-form').value;
                    cmd += ` \\\n  -H "Content-Type: application/x-www-form-urlencoded" \\\n  -d "${form}"`;
                }
                code = cmd;
            } else if (lang === 'python') {
                let pyUrl = url;
                if (mode === 'query') pyUrl += '?' + document.getElementById('gen-query').value;
                let py = `import requests\n\nurl = "${pyUrl}"\n`;
                if (mode === 'payload') {
                    py += `payload = ${document.getElementById('gen-payload').value}\nresponse = requests.${method.toLowerCase()}(url, json=payload)`;
                } else if (mode === 'text') {
                    py += `data = ` + JSON.stringify(document.getElementById('gen-text').value) + `\nheaders = {"Content-Type": "text/plain"}\nresponse = requests.${method.toLowerCase()}(url, data=data, headers=headers)`;
                } else if (mode === 'file') {
                    let filepath = document.getElementById('gen-file').value.replace(/^@/, '');
                    py += `files = {'file': open('${filepath}', 'rb')}\nresponse = requests.${method.toLowerCase()}(url, files=files)`;
                } else if (mode === 'file_content') {
                    let filepath = document.getElementById('gen-file-content').value.replace(/^@/, '');
                    py += `data = open('${filepath}', 'rb').read()\nheaders = {"Content-Type": "text/plain"}\nresponse = requests.${method.toLowerCase()}(url, data=data, headers=headers)`;
                } else if (mode === 'form') {
                    py += `data = "${document.getElementById('gen-form').value}"\nheaders = {"Content-Type": "application/x-www-form-urlencoded"}\nresponse = requests.${method.toLowerCase()}(url, data=data, headers=headers)`;
                } else {
                    py += `response = requests.${method.toLowerCase()}(url)`;
                }
                py += `\nprint(response.status_code, response.text)`;
                code = py;
            } else if (lang === 'js') {
                let jsUrl = url;
                if (mode === 'query') jsUrl += '?' + document.getElementById('gen-query').value;
                let js = `fetch("${jsUrl}", {\n  method: "${method}"`;
                if (mode === 'payload') {
                    js += `,\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify(${document.getElementById('gen-payload').value})`;
                } else if (mode === 'text') {
                    js += `,\n  headers: { "Content-Type": "text/plain" },\n  body: ${JSON.stringify(document.getElementById('gen-text').value)}`;
                } else if (mode === 'form') {
                    js += `,\n  headers: { "Content-Type": "application/x-www-form-urlencoded" },\n  body: "${document.getElementById('gen-form').value}"`;
                } else if (mode === 'file') {
                    js += `,\n  body: formData // append file to FormData object`;
                } else if (mode === 'file_content') {
                    js += `,\n  headers: { "Content-Type": "text/plain" },\n  body: fileContent // raw content of local file`;
                }
                js += `\n})\n.then(res => res.text())\n.then(console.log);`;
                code = js;
            } else if (lang === 'powershell') {
                let psUrl = url;
                if (mode === 'query') psUrl += '?' + document.getElementById('gen-query').value;
                let ps = `Invoke-RestMethod -Uri "${psUrl}" -Method ${method}`;
                if (mode === 'payload') {
                    ps += ` -ContentType 'application/json' -Body '${document.getElementById('gen-payload').value}'`;
                } else if (mode === 'text') {
                    ps += ` -ContentType 'text/plain' -Body '${document.getElementById('gen-text').value}'`;
                } else if (mode === 'form') {
                    ps += ` -ContentType 'application/x-www-form-urlencoded' -Body '${document.getElementById('gen-form').value}'`;
                } else if (mode === 'file_content') {
                    let filepath = document.getElementById('gen-file-content').value.replace(/^@/, '');
                    ps += ` -ContentType 'text/plain' -InFile '${filepath}'`;
                }
                code = ps;
            } else if (lang === 'powershell') {
                let psUrl = url;
                if (mode === 'query') psUrl += '?' + document.getElementById('gen-query').value;
                let ps = `Invoke-RestMethod -Uri "${psUrl}" -Method ${method}`;
                if (mode === 'payload') {
                    ps += ` -ContentType 'application/json' -Body '${document.getElementById('gen-payload').value}'`;
                } else if (mode === 'text') {
                    ps += ` -ContentType 'text/plain' -Body '${document.getElementById('gen-text').value}'`;
                } else if (mode === 'form') {
                    ps += ` -ContentType 'application/x-www-form-urlencoded' -Body '${document.getElementById('gen-form').value}'`;
                }
                code = ps;
            }

            document.getElementById('curl-out').innerText = code;
        }

        async function sendTestRequest() {
            const host = document.getElementById('gen-host').value.replace(new RegExp('/$'), '');
            const method = document.getElementById('gen-method').value;
            const subpath = document.getElementById('gen-subpath').value;
            const mode = document.getElementById('gen-mode').value;

            let url = host + subpath;
            let options = { method: method };

            if (mode === 'payload') {
                options.headers = { 'Content-Type': 'application/json' };
                options.body = document.getElementById('gen-payload').value;
            } else if (mode === 'text') {
                options.headers = { 'Content-Type': 'text/plain' };
                options.body = document.getElementById('gen-text').value;
            } else if (mode === 'query') {
                const q = document.getElementById('gen-query').value;
                url += (url.includes('?') ? '&' : '?') + q;
            } else if (mode === 'form') {
                options.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
                options.body = document.getElementById('gen-form').value;
            }

            const btn = document.getElementById('btn-send');
            btn.innerText = '⏳ Sending...';
            btn.disabled = true;

            try {
                await fetch(url, options);
                btn.innerText = '✅ Sent!';
                setTimeout(() => { btn.innerText = '🚀 Send Test Request'; btn.disabled = false; }, 1200);
                fetchLogs();
            } catch (e) {
                alert('Error sending request: ' + e.message);
                btn.innerText = '🚀 Send Test Request';
                btn.disabled = false;
            }
        }

        function copyGeneratedCode() {
            const text = document.getElementById('curl-out').innerText;
            navigator.clipboard.writeText(text);
            const btn = document.getElementById('btn-copy');
            const orig = btn.innerText;
            btn.innerText = '✅ Copied!';
            setTimeout(() => { btn.innerText = orig; }, 1200);
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs_json');
                const logs = await res.json();
                
                const currentHash = JSON.stringify(logs);
                if (currentHash === lastLogHash) return;
                lastLogHash = currentHash;
                cachedLogs = logs;

                document.getElementById('stat-total').innerText = logs.length;
                document.getElementById('stat-get').innerText = logs.filter(l => l.method==='GET').length;
                document.getElementById('stat-post').innerText = logs.filter(l => l.method==='POST').length;
                document.getElementById('stat-put').innerText = logs.filter(l => l.method==='PUT').length;
                document.getElementById('stat-delete').innerText = logs.filter(l => l.method==='DELETE').length;
                document.getElementById('stat-patch').innerText = logs.filter(l => l.method==='PATCH').length;
                document.getElementById('stat-options').innerText = logs.filter(l => l.method==='OPTIONS').length;
                document.getElementById('stat-head').innerText = logs.filter(l => l.method==='HEAD').length;
                document.getElementById('stat-trace').innerText = logs.filter(l => l.method==='TRACE').length;
                document.getElementById('stat-other').innerText = logs.filter(l => !['GET','POST','PUT','DELETE','PATCH','OPTIONS','HEAD','TRACE'].includes(l.method)).length;

                filterLogs();
            } catch (e) {}
        }

        function getBadgeClass(method) {
            const known = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD', 'TRACE'];
            return known.includes(method) ? `badge-${method}` : 'badge-OTHER';
        }

        function getIdentifierBadge(item) {
            if (item.files && item.files.length > 0) {
                return `<span class="data-badge badge-file-type">📁 File (${item.files.length})</span>`;
            }
            if (item.body && item.body_type === 'json') {
                return `<span class="data-badge badge-payload-type">📦 JSON Payload</span>`;
            }
            if (item.body && item.body.trim().length > 0) {
                return `<span class="data-badge badge-text-type">📝 Text Body</span>`;
            }
            if (item.form_data && Object.keys(item.form_data).length > 0) {
                return `<span class="data-badge badge-form-type">📄 Form Data</span>`;
            }
            if (item.query_params && Object.keys(item.query_params).length > 0) {
                return `<span class="data-badge badge-query-type">🔗 Query Params</span>`;
            }
            return `<span class="data-badge badge-empty-type">⚪ Empty</span>`;
        }

        function buildItemCurl(item) {
            let cmd = `curl -X ${item.method} "${item.url}"`;
            if (item.method === 'HEAD') {
                cmd = `curl -I "${item.url}"`;
            } else if (item.body) {
                cmd += ` \\\n  -H "Content-Type: ${item.content_type || 'application/json'}" \\\n  -d '${item.body.replace(/'/g, "'\\\\''")}'`;
            } else if (item.files && item.files.length) {
                cmd += ` \\\n  -F "file=@${item.files[0].filename}"`;
            }
            return cmd;
        }

        function renderFiles(files) {
            if (!files || !files.length) return '';
            return `<div class="section-sub">📁 Uploaded Files (${files.length})</div>` +
                files.map(f => {
                    const dataUrl = f.storage_url || f.data_uri || '';
                    const isImg = (f.content_type && f.content_type.startsWith('image/')) ||
                                  /\\.(png|jpe?g|gif|webp|svg|bmp|ico)$/i.test(f.filename);
                    const isText = f.is_text || (f.plain_content && !f.plain_content.startsWith('<raw binary') && !f.plain_content.startsWith('<binary'));

                    return `
                    <div class="file-box" style="flex-direction: column; align-items: flex-start;">
                        <div style="width: 100%; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                            <div>
                                <strong>📄 ${escapeHtml(f.filename)}</strong>
                                <small style="color:#8b949e">(${formatBytes(f.size_bytes)} | MD5: ${f.md5})</small>
                                ${f.storage_url ? `<br><small style="color:#58a6ff">🌐 Object Storage: <a href="${f.storage_url}" target="_blank" style="color:#58a6ff;">${f.storage_url}</a></small>` : ''}
                            </div>
                            ${dataUrl ? `<a href="${dataUrl}" class="btn" target="_blank" download="${escapeHtml(f.filename)}">📥 Download / View File</a>` : ''}
                        </div>
                        
                        ${isImg && dataUrl ? `<img src="${dataUrl}" class="img-preview" alt="${escapeHtml(f.filename)}">` : ''}
                        
                        ${isText ? `
                        <div style="width: 100%; margin-top: 6px;">
                            <small style="color:#8b949e">Raw Plain Content:</small>
                            <pre style="margin-top: 4px;">${escapeHtml(f.plain_content)}</pre>
                        </div>
                        ` : ''}
                    </div>
                `}).join('');
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024, sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
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
                            <span class="method-badge ${getBadgeClass(item.method)}">${item.method}</span>
                            <span>${escapeHtml(item.path)}</span>
                            ${getIdentifierBadge(item)}
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

                        ${renderFiles(item.files)}

                        <div class="section-sub">cURL Replay Command</div>
                        <pre>${escapeHtml(buildItemCurl(item))}</pre>
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
        timestamp = get_ist_now_str()
        
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
    response.headers["Content-Disposition"] = f"attachment; filename=api_logs_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}_IST.json"
    return response

@flask_app.route("/export/csv", methods=["GET"])
def export_csv():
    response = make_response(db.export_logs_csv())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename=api_logs_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}_IST.csv"
    return response

@flask_app.route("/healthz", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "api-sniffer-listener",
        "total_logged": db.get_total_count(),
        "timestamp": get_ist_now_str()
    }), 200

# Catch-all endpoint handler for ALL HTTP methods including OPTIONS, HEAD, TRACE, CONNECT & custom methods
ALL_HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"]

@flask_app.route("/api/<path:subpath>", methods=ALL_HTTP_METHODS)
@flask_app.route("/webhook/<path:subpath>", methods=ALL_HTTP_METHODS)
@flask_app.route("/capture/<path:subpath>", methods=ALL_HTTP_METHODS)
@flask_app.route("/hook/<path:subpath>", methods=ALL_HTTP_METHODS)
def catch_all(subpath=""):
    start_time = time.time()
    req_id = str(uuid.uuid4())
    timestamp = get_ist_now_str()

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
            file_bytes = file_obj.read()
            file_size = len(file_bytes)
            md5_hash = hashlib.md5(file_bytes).hexdigest()
            content_type = file_obj.content_type or "application/octet-stream"

            # External Object Storage Upload (Catbox.moe - Raw Un-encoded Public Object Storage)
            storage_url = None
            try:
                cat_res = requests.post(
                    "https://catbox.moe/user/api.php",
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": (orig_filename, file_bytes, content_type)},
                    timeout=5
                )
                if cat_res.status_code == 200 and cat_res.text.strip().startswith("http"):
                    storage_url = cat_res.text.strip()
            except Exception:
                storage_url = None

            # Base64 fallback Data URI if external storage offline
            b64_str = base64.b64encode(file_bytes).decode("utf-8")
            data_uri = storage_url or f"data:{content_type};base64,{b64_str}"

            is_text = False
            try:
                plain_content = file_bytes.decode("utf-8")
                is_text = True
            except UnicodeDecodeError:
                plain_content = f"<binary file: {file_size} bytes, md5: {md5_hash}>"

            files_info.append({
                "field": file_key,
                "filename": orig_filename,
                "size_bytes": file_size,
                "md5": md5_hash,
                "content_type": content_type,
                "is_text": is_text,
                "plain_content": plain_content,
                "storage_url": storage_url,
                "data_uri": data_uri
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
