<img src="../../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120"/> 🌐 Entelgia API Documentation

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

**Last Updated:** February 2026
