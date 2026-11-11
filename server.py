#!/usr/bin/env python3
"""
خادم محلي وقاعدة بيانات دائمة (SQLite) لنادي البرمجة والذكاء الاصطناعي Coding AI.
يحفظ كافة تسجيلات الطلبة في ملف قاعدة بيانات حقيقي (coding_ai_database.db)
لا يضيع عند إغلاق المتصفح أو إعادة تشغيل الحاسوب.
"""

import hashlib
import json
import os
import secrets
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "coding_ai_database.db")
PORT = int(os.environ.get("PORT", 3000))

# SHA-256 Hash لكلمة مرور الأدمن (بدون تخزين كلمة المرور كنص صريح)
ADMIN_PASS_HASH = "b24adf0413cc0e4a1109b8af3363f3abe50940b8c7f15867621ea658e5325534"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                account TEXT,
                fullName TEXT NOT NULL,
                major TEXT,
                academicYear TEXT,
                telegramUser TEXT,
                hasExperience TEXT,
                knownTech TEXT,
                interestDomains TEXT,
                committeeJoin TEXT,
                offeredSkills TEXT,
                learningTopics TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    conn.close()


def row_to_dict(row):
    def parse_json_list(val):
        if not val:
            return []
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except Exception:
            return [v.strip() for v in str(val).split("|") if v.strip()]

    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "account": row["account"],
        "fullName": row["fullName"],
        "major": row["major"],
        "academicYear": row["academicYear"],
        "telegramUser": row["telegramUser"],
        "hasExperience": row["hasExperience"],
        "knownTech": row["knownTech"],
        "interestDomains": parse_json_list(row["interestDomains"]),
        "committeeJoin": row["committeeJoin"],
        "offeredSkills": row["offeredSkills"],
        "learningTopics": parse_json_list(row["learningTopics"]),
    }


def serialize_list(val):
    if isinstance(val, list):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        return json.dumps([v.strip() for v in val.split("|") if v.strip()], ensure_ascii=False)
    return "[]"


class CodingAIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None

    def is_admin_authorized(self):
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header[7:].strip()
        if not token:
            return False
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT token FROM sessions WHERE token = ?", (token,)).fetchone()
            return row is not None
        finally:
            conn.close()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            conn = get_db_connection()
            try:
                count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
                sheet_row = conn.execute("SELECT value FROM settings WHERE key = 'sheet_url'").fetchone()
                sheet_url = sheet_row["value"] if sheet_row else ""
            finally:
                conn.close()
            return self.send_json(200, {
                "ok": True,
                "storage": "sqlite",
                "dbFile": "coding_ai_database.db",
                "totalResponses": count,
                "sheetUrl": sheet_url,
            })

        if path == "/api/config":
            conn = get_db_connection()
            try:
                sheet_row = conn.execute("SELECT value FROM settings WHERE key = 'sheet_url'").fetchone()
                sheet_url = sheet_row["value"] if sheet_row else ""
            finally:
                conn.close()
            return self.send_json(200, {"ok": True, "sheetUrl": sheet_url})

        if path == "/api/responses":
            if not self.is_admin_authorized():
                return self.send_json(401, {"ok": False, "error": "غير مصرح به. يرجى تسجيل الدخول أولاً."})
            conn = get_db_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM responses ORDER BY created_at DESC, rowid DESC"
                ).fetchall()
                return self.send_json(200, {"ok": True, "responses": [row_to_dict(r) for r in rows]})
            finally:
                conn.close()

        # منع الوصول المباشر لملف قاعدة البيانات أو السكربتات الحساسة عبر HTTP
        if path in ("/coding_ai_database.db", "/server.py"):
            return self.send_json(403, {"ok": False, "error": "Forbidden"})

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/admin/login":
            data = self.read_json_body()
            if data is None:
                return self.send_json(400, {"ok": False, "error": "Invalid JSON"})
            password = str(data.get("password", ""))
            pass_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
            if pass_hash != ADMIN_PASS_HASH:
                return self.send_json(401, {"ok": False, "error": "كلمة المرور غير صحيحة"})

            token = secrets.token_hex(32)
            conn = get_db_connection()
            with conn:
                conn.execute("INSERT INTO sessions (token) VALUES (?)", (token,))
            conn.close()
            return self.send_json(200, {"ok": True, "token": token})

        if path == "/api/responses":
            data = self.read_json_body()
            if not data or not data.get("fullName"):
                return self.send_json(400, {"ok": False, "error": "الاسم الكامل مطلوب"})

            rec_id = str(data.get("id") or f"GF-{secrets.token_hex(4).upper()}")
            conn = get_db_connection()
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO responses (
                        id, timestamp, account, fullName, major, academicYear,
                        telegramUser, hasExperience, knownTech, interestDomains,
                        committeeJoin, offeredSkills, learningTopics
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec_id,
                        str(data.get("timestamp", "")),
                        str(data.get("account", "")),
                        str(data.get("fullName", "")),
                        str(data.get("major", "")),
                        str(data.get("academicYear", "")),
                        str(data.get("telegramUser", "")),
                        str(data.get("hasExperience", "")),
                        str(data.get("knownTech", "")),
                        serialize_list(data.get("interestDomains", [])),
                        str(data.get("committeeJoin", "")),
                        str(data.get("offeredSkills", "")),
                        serialize_list(data.get("learningTopics", [])),
                    ),
                )
            conn.close()
            return self.send_json(201, {"ok": True, "id": rec_id})

        if path == "/api/sync-import":
            if not self.is_admin_authorized():
                return self.send_json(401, {"ok": False, "error": "غير مصرح به"})
            data = self.read_json_body()
            items = data.get("responses", []) if isinstance(data, dict) else []
            if not isinstance(items, list):
                return self.send_json(400, {"ok": False, "error": "Invalid responses list"})

            inserted = 0
            conn = get_db_connection()
            with conn:
                for item in items:
                    if not isinstance(item, dict) or not item.get("fullName"):
                        continue
                    rec_id = str(item.get("id") or f"GF-{secrets.token_hex(4).upper()}")
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO responses (
                            id, timestamp, account, fullName, major, academicYear,
                            telegramUser, hasExperience, knownTech, interestDomains,
                            committeeJoin, offeredSkills, learningTopics
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rec_id,
                            str(item.get("timestamp", "")),
                            str(item.get("account", "")),
                            str(item.get("fullName", "")),
                            str(item.get("major", "")),
                            str(item.get("academicYear", "")),
                            str(item.get("telegramUser", "")),
                            str(item.get("hasExperience", "")),
                            str(item.get("knownTech", "")),
                            serialize_list(item.get("interestDomains", [])),
                            str(item.get("committeeJoin", "")),
                            str(item.get("offeredSkills", "")),
                            serialize_list(item.get("learningTopics", [])),
                        ),
                    )
                    inserted += cur.rowcount
            conn.close()
            return self.send_json(200, {"ok": True, "imported": inserted})

        if path == "/api/config":
            if not self.is_admin_authorized():
                return self.send_json(401, {"ok": False, "error": "غير مصرح به"})
            data = self.read_json_body()
            if data is None:
                return self.send_json(400, {"ok": False, "error": "Invalid JSON"})
            sheet_url = str(data.get("sheetUrl", "")).strip()
            conn = get_db_connection()
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES ('sheet_url', ?)",
                    (sheet_url,),
                )
            conn.close()
            return self.send_json(200, {"ok": True, "sheetUrl": sheet_url})

        return self.send_json(404, {"ok": False, "error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if not self.is_admin_authorized():
            return self.send_json(401, {"ok": False, "error": "غير مصرح به"})

        if path == "/api/responses":
            conn = get_db_connection()
            with conn:
                conn.execute("DELETE FROM responses")
            conn.close()
            return self.send_json(200, {"ok": True})

        if path.startswith("/api/responses/"):
            rec_id = path[len("/api/responses/"):].strip()
            if not rec_id:
                return self.send_json(400, {"ok": False, "error": "Missing ID"})
            conn = get_db_connection()
            with conn:
                conn.execute("DELETE FROM responses WHERE id = ?", (rec_id,))
            conn.close()
            return self.send_json(200, {"ok": True})

        return self.send_json(404, {"ok": False, "error": "Not found"})


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), CodingAIHandler)
    print(f"Coding AI Server running on http://localhost:{PORT}")
    print(f"Database file: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("Server stopped.")

