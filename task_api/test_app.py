import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server


class TaskAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.database = Path(cls.temp.name) / "test.sqlite3"
        cls.token = "test-token-portfolio"
        cls.server = create_server("127.0.0.1", 0, cls.database, cls.token)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("DELETE FROM tasks")

    def request(self, method, path, body=None, authorized=True):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + self.token
        try:
            response = urlopen(Request(self.base + path, data=data, headers=headers, method=method), timeout=5)
        except HTTPError as error:
            response = error
        return response.code, json.loads(response.read())

    def test_create_read_update_delete(self):
        status, task = self.request("POST", "/tasks", {"title": " Review export ", "description": "Synthetic demo"})
        self.assertEqual(status, 201)
        self.assertEqual(task["title"], "Review export")
        path = f"/tasks/{task['id']}"
        self.assertEqual(self.request("GET", path)[1]["status"], "todo")
        self.assertEqual(self.request("PATCH", path, {"status": "done"})[1]["status"], "done")
        self.assertEqual(self.request("DELETE", path)[0], 200)
        self.assertEqual(self.request("GET", path)[0], 404)

    def test_authentication_is_required(self):
        self.assertEqual(self.request("GET", "/tasks", authorized=False)[0], 401)
        self.assertEqual(self.request("GET", "/health", authorized=False)[0], 200)

    def test_invalid_title_does_not_create_task(self):
        for payload in ({}, {"title": " "}, {"title": 25}, {"title": "x" * 201}):
            self.assertEqual(self.request("POST", "/tasks", payload)[0], 400)
        self.assertEqual(self.request("GET", "/tasks")[1]["total"], 0)

    def test_validation_keeps_existing_data(self):
        _, task = self.request("POST", "/tasks", {"title": "Keep this"})
        path = f"/tasks/{task['id']}"
        for payload in ({"status": "unknown"}, {"status": []}, {"title": None}, {"extra": 1}):
            self.assertEqual(self.request("PATCH", path, payload)[0], 400)
        self.assertEqual(self.request("GET", path)[1]["title"], "Keep this")

    def test_pagination_and_filter(self):
        for index in range(3):
            _, task = self.request("POST", "/tasks", {"title": f"Task {index}"})
        self.request("PATCH", f"/tasks/{task['id']}", {"status": "done"})
        status, result = self.request("GET", "/tasks?limit=1&offset=1")
        self.assertEqual((status, result["total"], len(result["items"])), (200, 3, 1))
        self.assertEqual(self.request("GET", "/tasks?status=done")[1]["total"], 1)
        for query in ("limit=0", "limit=101", "offset=-1", "limit=no", "status=no"):
            self.assertEqual(self.request("GET", "/tasks?" + query)[0], 400)

    def test_input_is_stored_as_data(self):
        title = "'; DROP TABLE tasks; --"
        self.assertEqual(self.request("POST", "/tasks", {"title": title})[0], 201)
        self.assertEqual(self.request("GET", "/tasks")[1]["items"][0]["title"], title)

    def test_changes_are_persisted_in_sqlite(self):
        _, task = self.request("POST", "/tasks", {"title": "Persist me"})
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT title FROM tasks WHERE id = ?", (task["id"],)).fetchone()[0], "Persist me")

    def test_unknown_route_and_method(self):
        self.assertEqual(self.request("GET", "/missing")[0], 404)
        self.assertEqual(self.request("PATCH", "/tasks", {"status": "done"})[0], 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
