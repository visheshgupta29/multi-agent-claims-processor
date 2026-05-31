# Troubleshooting Guide — Issues & Resolutions

This document captures every problem encountered during development and deployment of the Plum Claims Processing System, along with the steps taken to resolve each.

---

## 1. Module Import Errors in Tests

**Problem:** Running `pytest tests/ -v` directly failed with `ModuleNotFoundError: No module named 'app'`.

**Root Cause:** The project uses a virtual environment; running `pytest` from the system Python didn't include the project root in `sys.path`.

**Resolution:**
- Always activate the venv and set `PYTHONPATH`:
  ```powershell
  $env:PYTHONPATH = "."
  & venv\Scripts\python.exe -m pytest tests/ -v
  ```
- This ensures the `app/` package is discoverable.

---

## 2. Async Fixture Deprecation in pytest-asyncio

**Problem:** Tests using `@pytest.fixture` for async fixtures raised:
```
DeprecationWarning: @pytest.fixture is not compatible with async fixtures in strict mode.
Use @pytest_asyncio.fixture instead.
```

**Root Cause:** pytest-asyncio `asyncio_mode = auto` (set in `pytest.ini`) requires async fixtures to use the `@pytest_asyncio.fixture` decorator, not the standard `@pytest.fixture`.

**Resolution:**
- Changed all async fixture decorators in `tests/test_api.py`:
  ```python
  import pytest_asyncio

  @pytest_asyncio.fixture
  async def client():
      ...
  ```
- Added `pytest.ini` with:
  ```ini
  [pytest]
  asyncio_mode = auto
  testpaths = tests
  ```

---

## 3. Python 3.14 Build Failure on Render

**Problem:** Render deployment failed with:
```
error: can't find Rust compiler
Building wheel for pydantic-core (PEP 517) ... error
```

**Root Cause:** Render auto-detected the latest Python (3.14) which had no pre-built binary wheels for `pydantic-core`. It attempted to compile from source, requiring a Rust toolchain not present in the build environment.

**Resolution:**
- Created `.python-version` file in project root:
  ```
  3.12.0
  ```
- Render reads this file and uses the specified Python version, which has pre-built wheels available for all dependencies.

---

## 4. Missing Root Endpoint

**Problem:** Visiting `https://plum-claims-api-ao0h.onrender.com/` returned a 404 or blank response — confusing for anyone verifying the deployment.

**Root Cause:** FastAPI had no route defined for `GET /`.

**Resolution:**
- Added a root endpoint in `app/main.py`:
  ```python
  @app.get("/")
  async def root():
      return {
          "system": "Plum Health Insurance Claims Processing System",
          "version": "1.0.0",
          "endpoints": { ... },
          "documentation": "/docs"
      }
  ```

---

## 5. Swagger UI CORS / Mixed-Content Error on Render

**Problem:** The `/docs` Swagger UI loaded correctly, but clicking "Try it out" on any endpoint showed:
```
Failed to fetch.
Possible Reasons: CORS, Network Failure
URL scheme must be "http" or "https" for CORS request.
```

**Root Cause:** Render terminates TLS at its edge proxy and forwards plain HTTP internally to the container. FastAPI's auto-generated OpenAPI schema used the internal `http://` scheme for server URLs. The browser blocked these as mixed-content (page served over HTTPS, API calls attempted over HTTP).

**Resolution Attempts:**

### Attempt 1: `root_path` + TrustedHostMiddleware (❌ Did not fix)
```python
root_path = os.environ.get("ROOT_PATH", "")
app = FastAPI(..., root_path=root_path)
```
- This approach requires manually setting `ROOT_PATH` env var and didn't address the scheme mismatch.

### Attempt 2: `--proxy-headers --forwarded-allow-ips='*'` (❌ Partial)
Updated `render.yaml` and `Procfile`:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```
- This tells uvicorn to trust `X-Forwarded-Proto` headers, but Render's proxy behavior didn't reliably propagate the scheme to FastAPI's OpenAPI generation.

### Attempt 3: Explicit `servers` in OpenAPI spec (✅ Fixed)
```python
_render_url = os.environ.get("RENDER_EXTERNAL_URL")  # Render sets this automatically
_servers = [{"url": _render_url, "description": "Production"}] if _render_url else None

app = FastAPI(..., servers=_servers)
```
- Render automatically injects `RENDER_EXTERNAL_URL=https://plum-claims-api-ao0h.onrender.com` into every service.
- By passing it to the `servers` parameter, Swagger UI uses the correct `https://` URL for all requests.
- Locally, when `RENDER_EXTERNAL_URL` is unset, `servers=None` and FastAPI uses its default behavior (relative URLs, which work fine).

---

## 6. `datetime.utcnow()` Deprecation Warnings

**Problem:** Tests emit warnings:
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal
in a future version. Use timezone-aware objects to represent datetimes in UTC.
```

**Root Cause:** Python 3.12 deprecated `datetime.utcnow()` in favor of `datetime.now(datetime.UTC)`.

**Status:** Cosmetic only — does not affect functionality. The warnings appear in `decision_aggregator.py`, `trace_store.py`, and `graph.py`. Left as-is since it doesn't impact correctness and the codebase targets Python 3.12 where it still works.

---

## 7. pytest Exit Code 1 in PowerShell (False Alarm)

**Problem:** `pytest` commands appeared to "fail" with exit code 1 in PowerShell, even when all tests passed.

**Root Cause:** PowerShell treats any output to stderr as a non-zero exit. pytest's deprecation warnings are written to stderr, triggering this behavior. The tests themselves pass — the exit code is a PowerShell artifact.

**Verification:** The test summary line always shows `X passed`, confirming success:
```
======================= 27 passed, 22 warnings in 1.12s =======================
```

---

## 8. Eval Runner Emoji Encoding on Windows

**Problem:** Running `python -m eval.runner` on Windows produced `UnicodeEncodeError` when printing emoji characters (✅, ❌, etc.) in the eval report.

**Root Cause:** Windows console defaults to `cp1252` encoding which can't render Unicode emoji.

**Resolution:**
```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m eval.runner
```

---

## 9. Hernia / Herniation False Positive in Policy Engine

**Problem:** A claim for "disc herniation" (legitimate spinal condition) was incorrectly flagged by the waiting period check for "hernia" (abdominal hernia surgery, which has a 2-year waiting period).

**Root Cause:** Simple substring matching — `"hernia" in "disc herniation"` returned True.

**Resolution:**
- Used specific medical terms for the waiting period exclusion check:
  ```python
  hernia_terms = ["hernia repair", "hernia surgery", "inguinal hernia", "umbilical hernia", "abdominal hernia"]
  ```
- The policy engine now checks against these specific compound terms rather than the bare substring "hernia", preventing false matches on unrelated conditions like disc herniation.

---

## 10. Render Free Tier Cold Start

**Problem:** First request to the deployed API after ~15 minutes of inactivity takes 30–60 seconds to respond.

**Root Cause:** Render free tier spins down idle services to conserve resources. On the next request, the container must cold-start (boot Python, load dependencies, initialize SQLite).

**Status:** Expected behavior on free tier. Not a bug. Documented for evaluators:
- First request: ~30-60s (cold start)
- Subsequent requests: ~1-3s (warm)

---

## Summary Table

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Module import in tests | Blocker | ✅ Fixed |
| 2 | Async fixture decorator | Warning | ✅ Fixed |
| 3 | Python 3.14 on Render | Blocker | ✅ Fixed |
| 4 | Missing root endpoint | UX | ✅ Fixed |
| 5 | Swagger CORS/HTTPS | Blocker | ✅ Fixed |
| 6 | utcnow() deprecation | Cosmetic | ⚠️ Acknowledged |
| 7 | PowerShell exit code | Cosmetic | ⚠️ Explained |
| 8 | Emoji encoding Windows | Minor | ✅ Fixed |
| 9 | Hernia false positive | Logic bug | ✅ Fixed |
| 10 | Render cold start | Expected | ⚠️ Documented |
