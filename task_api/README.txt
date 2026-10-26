Task API with SQLite

Self-initiated portfolio demonstration. AI-assisted implementation. This is
not a paid client project. It contains no client data or credentials.

Run with Python 3.10 or newer. No third-party packages are required.

Linux / macOS:
  TASK_API_TOKEN=local-demo-token-change-me python3 app.py

PowerShell:
  $env:TASK_API_TOKEN = 'local-demo-token-change-me'
  python app.py

The default address is http://127.0.0.1:8765. Data is persisted in tasks.sqlite3.
The token is supplied in an Authorization: Bearer <token> header.

Endpoints:
  GET    /health                  Local service health; no token required
  POST   /tasks                   JSON: title and optional description
  GET    /tasks?limit=20&offset=0  Paginated collection
  GET    /tasks?status=done        Filter by todo, doing or done
  GET    /tasks/1                 Read one task
  PATCH  /tasks/1                 Update title, description or status
  DELETE /tasks/1                 Delete one task

Example request:
  curl -H 'Authorization: Bearer local-demo-token-change-me' \
    -H 'Content-Type: application/json' \
    -d '{"title":"Review weekly report"}' http://127.0.0.1:8765/tasks

Run verification from this directory:
  python3 -m unittest -v

The tests exercise HTTP requests, authentication, CRUD, validation, pagination,
filtering, persistence and SQL input handling. The demo defaults to local-only
use. A public deployment needs HTTPS, operational monitoring and a deployment
configuration appropriate to the customer's environment.
