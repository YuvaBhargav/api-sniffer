# 🛰️ Low-Level Design (LLD) & System Architecture Specification

**Project Name:** API Request Sniffer Engine  
**Version:** 2.0 (IST Timezone & Zero-Disk Storage)  
**Author:** Engineering Team & Antigravity AI  
**Date:** September 2026  
**PDF Document:** [API_Sniffer_LLD_Architecture.pdf](file:///d:/api/api-sniffer/API_Sniffer_LLD_Architecture.pdf)

---

## 1. Executive Summary & Core Objectives

The **API Request Sniffer Engine** is a lightweight, high-performance request inspection and query generator platform. It provides real-time capture, un-redacted logging, and visual inspection of incoming HTTP requests across all standard methods (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `HEAD`, `TRACE`).

### Key Architecture Features
1. **Un-redacted Logging:** Full capture of HTTP headers, raw query strings, JSON payloads, form data, client IP, and cookies without masking.
2. **IST Timezone Standardization:** Native formatting of all log timestamps in Indian Standard Time (`UTC+5:30`).
3. **Zero Transit Encoding or Encryption:** Incoming files and request payloads are captured and transmitted in raw, un-modified binary/text format without any Base64 encoding, obfuscation, or encryption in transit.
4. **Temporary External Storage (`tmpfiles.org`):** Uploaded files are sent directly to `tmpfiles.org` API (`0 bytes` stored on server disk). The generated `tmpfiles.org` URL and MD5 checksum are logged directly to the UI without image previews or Base64 data strings.
5. **Multi-Language Query Generator:** Built-in generator capable of constructing ready-to-run queries across 7 data modes in cURL, Python (requests), JavaScript (fetch), and PowerShell.
6. **Minimalist Zero-Lag UI:** Single-page dark dashboard featuring instant search filtering, real-time polling, and interactive in-browser request execution.

---

## 2. High-Level Architecture Diagram

```
+------------------------------------+        +----------------------------------------+
|       API Clients & cURL           |        |           Web Dashboard UI             |
|   cURL / Postman / Mobile / Web    |        |       HTML5 / JS SPA / Dark Theme      |
+-----------------+------------------+        +-------------------+--------------------+
                  |                                               |
                  | HTTP/HTTPS (Raw Un-encoded)                   | Send Test / Poll
                  v                                               v
+--------------------------------------------------------------------------------------+
|                           Flask WSGI Server (app.py)                                 |
|               Wildcard Listener / Un-redacted Parser / Proxy-Aware                   |
+-----------------+-----------------------------------------------+--------------------+
                  |                                               |
                  v Store Logs & tmpfiles.org URLs                v Generate Code
+------------------------------------+        +----------------------------------------+
|      SQLite Database (db.py)       |        |        Query Generator Engine          |
|  Thread-Safe Connection Pool & DB  |        |    7 Data Modes: cURL/Py/JS/PS Snippets|
+------------------------------------+        +----------------------------------------+
```

---

## 3. Component Details (LLD)

### 3.1 Ingestion Layer (`app.py`)
- **Route Catch-All:** `catch_all_api(subpath)` handles all non-dashboard requests across HTTP methods.
- **Raw File Handling & External Storage:** File streams (`request.files`) are processed without any Base64 encoding or encryption. Bytes are forwarded directly to `https://tmpfiles.org/api/v1/upload`:
  ```python
  upload_res = requests.post(
      "https://tmpfiles.org/api/v1/upload",
      files={"file": (orig_filename, file_bytes, content_type)},
      timeout=10
  )
  ```
- **IST Timestamp Formatter:** Uses `datetime.now(IST)` to stamp exact arrival time in Indian Standard Time (`UTC+5:30`).

### 3.2 Database Engine (`db.py`)
- **Connection Pool:** Uses Python `sqlite3` with thread-local storage and WAL journal mode.
- **JSON Serialization:** Complex dictionary structures (`headers`, `query_params`, `form_data`, `files`) are stored as serialized text columns.

### 3.3 Query Generator Engine
Constructs ready-to-run code across 6 request types:
- `payload`: `application/json`
- `text`: `text/plain`
- `file`: `multipart/form-data`
- `query`: `URL query string`
- `form`: `application/x-www-form-urlencoded`
- `empty`: Headers only

Supported output formats:
- **cURL Command**
- **Python (`requests`)**
- **JavaScript (`fetch`)**
- **PowerShell (`Invoke-RestMethod`)**

---

## 4. Database Schema (`sniffer_logs`)

| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Internal log ID |
| `request_id` | `TEXT` | `NOT NULL, UNIQUE` | UUID v4 string |
| `timestamp` | `TEXT` | `NOT NULL` | IST formatted string |
| `method` | `TEXT` | `NOT NULL` | `GET`, `POST`, `PUT`, `DELETE`, etc. |
| `url` | `TEXT` | `NOT NULL` | Full request URL |
| `path` | `TEXT` | `NOT NULL` | Request URL path |
| `query_params` | `TEXT` | `DEFAULT '{}'` | Serialized JSON query params |
| `headers` | `TEXT` | `NOT NULL` | Serialized JSON request headers |
| `body_type` | `TEXT` | `NOT NULL` | `payload` / `text` / `file` / `form` / `empty` |
| `body` | `TEXT` | `DEFAULT ''` | Raw payload or formatted text |
| `files` | `TEXT` | `DEFAULT '[]'` | Base64 Data URIs, MD5, metadata |
| `client_ip` | `TEXT` | `NOT NULL` | Client IP address |

---

## 5. Sequence & Execution Flow

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

## 6. Verification & Test Suite Matrix

All endpoints and data modes verified via `py test_sniffer.py`:
- `GET` with Query String: **PASS**
- `POST` with JSON Payload: **PASS**
- `PUT` with Raw Text Body: **PASS**
- `PATCH` with Resource Body: **PASS**
- `DELETE` Request: **PASS**
- `OPTIONS` Preflight: **PASS**
- `POST` Multipart File Upload (Zero-Disk Base64): **PASS**
