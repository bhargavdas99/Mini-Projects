# Django + Redis High-Performance Backend Lab

A practical, hands-on micro-project demonstrating key distributed backend engineering patterns using **Django**, **Redis**, and **Docker**.

---

## 📌 Architecture & Design Patterns

This repository implements two fundamental backend architectural patterns:

### 1. Atomic Distributed Lock / Cooldown Rate-Limiter
- **Problem**: In concurrent or high-traffic environments, multiple requests or workers might attempt to trigger duplicate operations (e.g., sending duplicate WhatsApp/SMS notifications or running duplicate background tasks).
- **Solution**: Uses Redis atomic primitive `SET key value NX EX timeout` (exposed via Django's `cache.add()`).
- **Mechanism**:
  - The first worker/request sets key `lock:send_notification:<user_id>`.
  - Subsequent requests for the same `user_id` fail instantly and return an **HTTP 429 Too Many Requests** response.
  - Retaining key TTL without immediate deletion enforces a **Rate-Limit Cooldown window**, ensuring strict idempotency across distributed worker instances.

### 2. Read-Through DB Query Caching
- **Problem**: Frequent, expensive database queries introduce latency and database CPU overhead.
- **Solution**: In-memory caching using Redis as a cache layer.
- **Mechanism**:
  - **Cache Hit**: Returns stored data directly from Redis in **~1 ms** (a ~2000x latency reduction compared to disk/DB I/O).
  - **Cache Miss**: Simulates querying PostgreSQL/DB (2s latency), caches the result in Redis with a 30-second TTL, and returns the payload.

---

## 🚀 Tech Stack

- **Framework**: Python 3.x / Django
- **In-Memory Store**: Redis (run via Docker container)
- **Caching Backend**: `django.core.cache.backends.redis.RedisCache`
- **Containerization**: Docker

---

## 🛠 Project Setup & Installation

### 1. Clone & Environment Setup
```bash
git clone <your-repo-url>
cd django_redis_lab

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install django redis gunicorn
```

### 2. Start Redis Container via Docker
```bash
docker run -d --name redis-lab -p 6379:6379 redis:latest
```

Verify Redis is running:
```bash
docker exec -it redis-lab redis-cli ping
# Expected output: PONG
```

### 3. Configure Django (`core/settings.py`)
Ensure your Redis backend configuration is present:
```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}
```

---

## 🧪 Testing the Endpoints

### Run Django Development Server
```bash
python manage.py runserver
```

---

### Endpoint 1: Rate-Limited Notification Trigger
**URL**: `GET /send-notification/?user_id=101`

**Simulating Parallel/Concurrent Requests using `curl`**:
```bash
# Terminal 1
curl "http://127.0.0.1:8000/send-notification/?user_id=101"

# Terminal 2 (Execute immediately within 1-2 seconds)
curl "http://127.0.0.1:8000/send-notification/?user_id=101"
```

**Responses**:
- **Terminal 1 (HTTP 200 OK)**:
  ```json
  {
    "status": "success",
    "message": "Notification successfully sent to user: 101!"
  }
  ```
- **Terminal 2 (HTTP 429 Too Many Requests)**:
  ```json
  {
    "status": "error",
    "message": "Notification processing already in progress for user 101. Request ignored."
  }
  ```

---

### Endpoint 2: Read-Through Cached Profile
**URL**: `GET /user/<user_id>/`

1. **First Request (Cache Miss)**:
   - Request duration: `~2000 ms`
   - Response:
     ```json
     {
       "source": "DATABASE (Simulated)",
       "data": {
         "id": 42,
         "username": "developer_42",
         "role": "Backend Engineer",
         "status": "Active"
       }
     }
     ```
2. **Second Request within 30s (Cache Hit)**:
   - Request duration: `~1 ms`
   - Response:
     ```json
     {
       "source": "CACHE (Redis)",
       "data": {
         "id": 42,
         "username": "developer_42",
         "role": "Backend Engineer",
         "status": "Active"
       }
     }
     ```

---

## 🔍 Inspecting Redis Live

Access the Redis CLI inside the Docker container to inspect live key creation and TTL expiration:

```bash
docker exec -it redis-lab redis-cli -n 1
```

```redis
# List active cached keys
KEYS *

# Check remaining TTL (Time To Live) in seconds
TTL :1:user_profile:42
TTL :1:lock:send_notification:101
```

---

## 🧹 Teardown

To stop and remove local resources:

```bash
# Stop Redis container
docker stop redis-lab && docker rm redis-lab

# Deactivate virtual environment
deactivate
```
