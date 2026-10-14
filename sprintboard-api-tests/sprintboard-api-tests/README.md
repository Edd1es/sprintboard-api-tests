# SprintBoard API + Automated API Test Suite

A small REST API (FastAPI) and a 20-case automated API test suite (pytest + requests + jsonschema).

```bash
pip install -r requirements.txt
pytest -v --html=report.html --self-contained-html
```

Test categories: CRUD/positive, JSON-schema contract, data-driven negative validation,
authentication (401), business rules (409 status transitions), and a response-time smoke test.
