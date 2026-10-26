"""A local, token-protected task API using only Python's standard library."""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

STATUSES = {"todo", "doing", "done"}
MAX_BODY = 65_536


def connect(path):
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def create_server(host, port, database, token):
    if not token or len(token) < 12:
        raise ValueError("Set a token of at least 12 characters.")
    database = str(Path(database).resolve())
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with connect(database) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'todo',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )""")

    class Handler(BaseHTTPRequestHandler):
        server_version = "PortfolioTaskAPI/1.0"

        def log_message(self, format, *args):
            # Do not log credentials or request bodies.
            pass

        def respond(self, status, payload):
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def body(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Invalid Content-Length.") from None
            if not 0 < length <= MAX_BODY:
                raise ValueError("JSON body must be 1 to 65536 bytes.")
            try:
                result = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValueError("Body must contain valid UTF-8 JSON.") from None
            if not isinstance(result, dict):
                raise ValueError("JSON body must be an object.")
            return result

        def dispatch(self, method):
            parsed = urlsplit(self.path)
            if parsed.path == "/health" and method == "GET":
                self.respond(200, {"status": "ok", "demo": True})
                return
            provided = self.headers.get("Authorization", "")
            if not hmac.compare_digest(provided.encode(), ("Bearer " + token).encode()):
                self.respond(401, {"error": "A valid Bearer token is required."})
                return
            match = re.fullmatch(r"/tasks(?:/([1-9][0-9]*))?", parsed.path)
            if not match:
                self.respond(404, {"error": "Route not found."})
                return
            task_id = int(match[1]) if match[1] else None
            try:
                with connect(database) as connection:
                    if method == "GET" and task_id is None:
                        query = parse_qs(parsed.query, keep_blank_values=True)
                        try:
                            limit = int(query.get("limit", ["20"])[0])
                            offset = int(query.get("offset", ["0"])[0])
                        except ValueError:
                            raise ValueError("limit and offset must be integers.") from None
                        if not 1 <= limit <= 100 or offset < 0:
                            raise ValueError("limit must be 1..100; offset must be nonnegative.")
                        status = query.get("status", [None])[0]
                        if status is not None and status not in STATUSES:
                            raise ValueError("status must be todo, doing or done.")
                        where, args = (" WHERE status = ?", [status]) if status else ("", [])
                        total = connection.execute("SELECT COUNT(*) FROM tasks" + where, args).fetchone()[0]
                        rows = connection.execute("SELECT * FROM tasks" + where + " ORDER BY id LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
                        self.respond(200, {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset})
                    elif method == "POST" and task_id is None:
                        payload = self.body()
                        if set(payload) - {"title", "description"}:
                            raise ValueError("Only title and description are accepted on creation.")
                        self.validate(payload, creating=True)
                        cursor = connection.execute("INSERT INTO tasks(title, description) VALUES (?, ?)", (payload["title"].strip(), payload.get("description", "")))
                        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
                        self.respond(201, dict(row))
                    elif task_id is not None and method in {"GET", "PATCH", "DELETE"}:
                        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                        if row is None:
                            self.respond(404, {"error": "Task not found."})
                        elif method == "GET":
                            self.respond(200, dict(row))
                        elif method == "DELETE":
                            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                            self.respond(200, {"deleted": task_id})
                        else:
                            payload = self.body()
                            self.validate(payload)
                            values = dict(row)
                            values.update(payload)
                            connection.execute("UPDATE tasks SET title = ?, description = ?, status = ? WHERE id = ?", (values["title"].strip(), values["description"], values["status"], task_id))
                            self.respond(200, dict(connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()))
                    else:
                        self.respond(405, {"error": "Method is not supported on this route."})
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except sqlite3.Error:
                self.respond(503, {"error": "Storage is temporarily unavailable."})

        @staticmethod
        def validate(payload, creating=False):
            if not payload or set(payload) - {"title", "description", "status"}:
                raise ValueError("Provide title, description or status.")
            if creating and "title" not in payload:
                raise ValueError("title is required.")
            if "title" in payload and (not isinstance(payload["title"], str) or not 1 <= len(payload["title"].strip()) <= 200):
                raise ValueError("title must contain 1..200 characters.")
            if "description" in payload and (not isinstance(payload["description"], str) or len(payload["description"]) > 2000):
                raise ValueError("description must be a string of at most 2000 characters.")
            if "status" in payload and (not isinstance(payload["status"], str) or payload["status"] not in STATUSES):
                raise ValueError("status must be todo, doing or done.")

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

        def do_PATCH(self):
            self.dispatch("PATCH")

        def do_DELETE(self):
            self.dispatch("DELETE")

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", default="tasks.sqlite3")
    arguments = parser.parse_args()
    service = create_server(arguments.host, arguments.port, arguments.database, os.environ.get("TASK_API_TOKEN", ""))
    print(f"Task API listening on http://{arguments.host}:{service.server_port}")
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.server_close()
