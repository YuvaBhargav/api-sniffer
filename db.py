import os
import json
import sqlite3
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniffer_logs.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            timestamp TEXT NOT NULL,
            method TEXT NOT NULL,
            url TEXT NOT NULL,
            path TEXT NOT NULL,
            query_params TEXT NOT NULL,
            raw_query_string TEXT NOT NULL,
            headers TEXT NOT NULL,
            cookies TEXT NOT NULL,
            client_ip TEXT NOT NULL,
            user_agent TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_length INTEGER DEFAULT 0,
            body_type TEXT NOT NULL,
            body TEXT NOT NULL,
            form_data TEXT NOT NULL,
            files TEXT NOT NULL,
            response_status INTEGER DEFAULT 200,
            duration_ms REAL DEFAULT 0.0
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON request_logs(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON request_logs(method);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_path ON request_logs(path);")
    conn.commit()
    conn.close()

def insert_log(log_data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO request_logs (
            request_id, timestamp, method, url, path,
            query_params, raw_query_string, headers, cookies,
            client_ip, user_agent, content_type, content_length,
            body_type, body, form_data, files, response_status, duration_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log_data.get("request_id", ""),
        log_data.get("timestamp", datetime.now().isoformat()),
        log_data.get("method", "GET").upper(),
        log_data.get("url", ""),
        log_data.get("path", "/"),
        json.dumps(log_data.get("query_params", {}), ensure_ascii=False),
        log_data.get("raw_query_string", ""),
        json.dumps(log_data.get("headers", {}), ensure_ascii=False),
        json.dumps(log_data.get("cookies", {}), ensure_ascii=False),
        log_data.get("client_ip", "127.0.0.1"),
        log_data.get("user_agent", ""),
        log_data.get("content_type", ""),
        log_data.get("content_length", 0),
        log_data.get("body_type", "raw"),
        log_data.get("body", ""),
        json.dumps(log_data.get("form_data", {}), ensure_ascii=False),
        json.dumps(log_data.get("files", []), ensure_ascii=False),
        log_data.get("response_status", 200),
        log_data.get("duration_ms", 0.0)
    ))
    conn.commit()
    conn.close()

def get_logs(
    limit: int = 500,
    offset: int = 0,
    method_filter: Optional[List[str]] = None,
    search_query: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM request_logs WHERE 1=1"
    params = []

    if method_filter:
        placeholders = ",".join(["?"] * len(method_filter))
        query += f" AND method IN ({placeholders})"
        params.extend([m.upper() for m in method_filter])

    if search_query:
        search_pattern = f"%{search_query}%"
        query += """ AND (
            path LIKE ? OR
            url LIKE ? OR
            query_params LIKE ? OR
            raw_query_string LIKE ? OR
            headers LIKE ? OR
            body LIKE ? OR
            form_data LIKE ? OR
            client_ip LIKE ?
        )"""
        params.extend([search_pattern] * 8)

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        item["query_params"] = json.loads(item["query_params"]) if item["query_params"] else {}
        item["headers"] = json.loads(item["headers"]) if item["headers"] else {}
        item["cookies"] = json.loads(item["cookies"]) if item["cookies"] else {}
        item["form_data"] = json.loads(item["form_data"]) if item["form_data"] else {}
        item["files"] = json.loads(item["files"]) if item["files"] else []
        result.append(item)

    return result

def get_total_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM request_logs;")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_method_stats() -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT method, COUNT(*) as cnt FROM request_logs GROUP BY method;")
    rows = cursor.fetchall()
    conn.close()
    return {row["method"]: row["cnt"] for row in rows}

def clear_logs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM request_logs;")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='request_logs';")
    conn.commit()
    conn.close()

def delete_log(log_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM request_logs WHERE id = ?;", (log_id,))
    conn.commit()
    conn.close()

def export_logs_json() -> str:
    logs = get_logs(limit=10000)
    return json.dumps(logs, indent=2, ensure_ascii=False)

def export_logs_csv() -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM request_logs ORDER BY id DESC;")
    rows = cursor.fetchall()
    
    output = io.StringIO()
    if rows:
        colnames = [column[0] for column in cursor.description]
        writer = csv.writer(output)
        writer.writerow(colnames)
        for row in rows:
            writer.writerow(list(row))
    conn.close()
    return output.getvalue()

init_db()
