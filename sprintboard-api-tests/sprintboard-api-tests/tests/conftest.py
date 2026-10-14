import os, subprocess, sys, time
import pytest, requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8765")
HEADERS = {"X-API-Key": "capstone-key"}


@pytest.fixture(scope="session", autouse=True)
def server():
    """Start the API once for the whole test session, then stop it."""
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", "8765"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            requests.get(BASE_URL + "/docs", timeout=0.2); break
        except requests.ConnectionError:
            time.sleep(0.1)
    yield
    proc.terminate()


@pytest.fixture
def api():
    """A requests.Session with the API key and a clean database for each test."""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.post(BASE_URL + "/reset")
    return s


@pytest.fixture
def make_task(api):
    def _make(title="Write test plan", priority=2, **extra):
        r = api.post(BASE_URL + "/tasks", json={"title": title, "priority": priority, **extra})
        assert r.status_code == 201, r.text
        return r.json()
    return _make
