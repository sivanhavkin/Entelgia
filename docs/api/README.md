<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="../../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">🌐 Entelgia API Documentation</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

## Overview

Entelgia provides a REST API for interacting with the multi-agent AI system.

**Base URL:** `http://localhost:8000`  
**API Version:** 1.0  
**Format:** JSON

---

## 🚀 Quick Start

### 1. Start the API Server

```bash
python Entelgia_production_meta.py api
```

The server will start on `http://localhost:8000`

### 2. Check Health Status

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.1"
}
```

### 3. Send Your First Message

**Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/chat",
    json={
        "message": "Hello, what's up?",
        "user_id": "demo_user"
    }
)

data = response.json()
print(data)
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "user_id": "user123"}'
```

---

## 📚 Interactive Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 🔌 Main Endpoints

### `POST /api/v1/chat`

Send a message to the AI agents and receive a response.

**Request:**
```json
{
  "message": "Your message here",
  "user_id": "unique_user_id",
  "session_id": "optional_session_id"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "reply": "Agent response",
    "agent": "Socrates",
    "emotion": "thoughtful",
    "timestamp": "2026-02-13T10:30:00Z"
  }
}
```

**Full documentation:** [See Interactive Docs](http://localhost:8000/docs)

---

## 📦 Python SDK Example

```python
import requests

class EntalgiaClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def chat(self, message: str, user_id: str):
        """Send a message to Entelgia."""
        response = requests.post(
            f"{self.base_url}/api/v1/chat",
            json={"message": message, "user_id": user_id}
        )
        return response.json()

# Usage
client = EntalgiaClient()
result = client.chat("What is the meaning of life?", "user_123")
print(result['data']['reply'])
```

---

## ⚠️ Error Handling

All errors return JSON:

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message"
  }
}
```

**Common Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid input)
- `500` - Server Error

---

## 🔐 Security Notes

- Currently runs without authentication (development mode)
- For production, implement API key authentication
- See: [Memory Security Documentation](../memory_security.md)

---

## 🌐 Web Research (v2.8.0)

The Web Research Module can be used directly from Python without the REST API.

### Python Usage

```python
from entelgia.web_research import maybe_add_web_context
from entelgia.fixy_research_trigger import fixy_should_search

# Check if a search is needed
needs_search = fixy_should_search("latest research on quantum computing")
# → True

# Run the full pipeline
context = maybe_add_web_context(
    user_message="latest research on quantum computing",
    db_path="entelgia_memory.db",   # optional: persist high-credibility sources
    max_results=5,
)
# → "External Research:\n\nSource 1:\n  Title: ...\n  URL: ...\n..."
```

### Individual Components

```python
from entelgia.web_tool import web_search, fetch_page_text, search_and_fetch, clear_failed_urls
from entelgia.source_evaluator import evaluate_sources
from entelgia.research_context_builder import build_research_context

# Search only
results = web_search("quantum computing 2026", max_results=3)

# Fetch single page — URLs that return 403 or 404 are automatically blacklisted
# and skipped on all subsequent calls within the same process.
page = fetch_page_text("https://arxiv.org/abs/2401.12345")

# Full bundle
bundle = search_and_fetch("AI regulation news")
scored = evaluate_sources(bundle["sources"])
context_block = build_research_context(bundle, scored)

# Reset the failed-URL blacklist (useful in tests or long-running processes)
clear_failed_urls()
```

### Per-Query Cooldown

`fixy_should_search` applies two independent cooldown layers so the same search
is never repeated too frequently:

```python
from entelgia.fixy_research_trigger import fixy_should_search, clear_trigger_cooldown

# First call fires
fixy_should_search("latest AI research")  # → True

# Same query within _COOLDOWN_TURNS turns is suppressed
fixy_should_search("latest AI research")  # → False

# A different query fires independently
fixy_should_search("latest quantum computing")  # → True

# Reset both per-trigger and per-query cooldown state
clear_trigger_cooldown()
```

---

## 📖 Additional Resources

- [Whitepaper](../../whitepaper.md)
- [Memory Security](../memory_security.md)
- [Contributing Guide](../../Contributing.md)
- [GitHub Repository](https://github.com/sivanhavkin/Entelgia)

---

## 💬 Support

- 🐛 **Issues:** [GitHub Issues](https://github.com/sivanhavkin/Entelgia/issues)
- 📧 **Contact:** Open an issue for questions

---

**Last Updated:** March 2026
