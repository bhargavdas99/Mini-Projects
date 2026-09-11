# Layer 7 Reverse Proxy & Round-Robin Load Balancer

A lightweight, custom **Layer 7 (L7) Reverse Proxy and Load Balancer** built from scratch in Python. This implementation demonstrates core backend architecture principles including **TCP connection termination**, **stateful Round-Robin traffic distribution**, **L7 header manipulation** (`X-Forwarded-For`), and **hop-by-hop header stripping**.

---

## Architecture Overview

```
                      +-------------------+
                      |   Client (curl)   |
                      +---------+---------+
                                |
                                | HTTP GET / POST (Port 8080)
                                v
                   +-------------------------+
                   |  L7 Reverse Proxy & LB  |
                   |       (proxy.py)        |
                   +------------+------------+
                                |
          +---------------------+---------------------+
          | Round-Robin Cycle   | Round-Robin Cycle   |
          v (Port 5001)         v (Port 5002)         |
+-------------------+ +-------------------+           |
|  Backend 1 Server | |  Backend 2 Server |           |
|   (backend.py)    | |   (backend.py)    |           |
+-------------------+ +-------------------+           |
```

### Key Engineering Concepts Implemented

1. **Layer 7 "Invasive" Inspection & Routing**
   Unlike Layer 4 load balancers (which route raw TCP packets based on IP:Port), this proxy terminates the incoming client TCP connection, decrypts/parses the HTTP payload at Layer 7, modifies headers, and initiates a secondary, independent TCP connection to an upstream backend server.

2. **Stateful Round-Robin Distribution**
   Uses Python's `itertools.cycle` to maintain an infinite circular sequence over upstream server endpoints (`http://127.0.0.1:5001` and `http://127.0.0.1:5002`), distributing requests evenly across the pool.

3. **Client Identity Preservation (`X-Forwarded-For`)**
   When the proxy opens the secondary connection to the backend, the backend's socket sees the proxy's IP. To ensure client visibility, the proxy extracts `request.remote_addr` from the incoming socket and injects the `X-Forwarded-For` HTTP header before forwarding.

4. **Host Header Normalization & Hop-by-Hop Stripping**
   - Strips the client's original `Host` header (`localhost:8080`) to allow the `requests` library to auto-populate the upstream server's host (`127.0.0.1:5001` / `5002`), preventing Virtual Host routing errors.
   - Strips single-hop transport headers (`Transfer-Encoding`, `Connection`, `Content-Encoding`) from the backend response prior to returning data to the client.

---

## Project Structure

```
mini-lb/
├── backend.py    # Multi-instance backend server with header introspection
├── proxy.py      # Layer 7 Reverse Proxy & Load Balancer
└── README.md     # Documentation
```

---

## Quickstart & Local Setup

### 1. Prerequisites & Environment Setup

Ensure you have Python 3.8+ installed:

```bash
git clone https://github.com/your-username/mini-lb.git
cd mini-lb

python3 -m venv .venv
source .venv/bin/activate
pip install flask requests
```

### 2. Running the System

Open 3 terminal windows/tabs:

**Terminal 1: Start Upstream Backend 1**
```bash
python backend.py 5001
```

**Terminal 2: Start Upstream Backend 2**
```bash
python backend.py 5002
```

**Terminal 3: Start the L7 Reverse Proxy**
```bash
python proxy.py
```

---

## Verification & Testing

Execute `curl` requests against the Reverse Proxy on port `8080`:

```bash
curl http://localhost:8080
```

### Expected Output (Round-Robin Demonstration)

**First Call (Routed to Backend 5001):**
```json
{
  "client_ip_seen": "127.0.0.1",
  "request_details": {
    "body": "",
    "headers": {
      "Accept": "*/*",
      "Accept-Encoding": "gzip, deflate",
      "Connection": "keep-alive",
      "Host": "127.0.0.1:5001",
      "User-Agent": "curl/8.5.0",
      "X-Forwarded-For": "127.0.0.1"
    },
    "method": "GET",
    "query_params": {},
    "url": "http://127.0.0.1:5001/"
  },
  "served_by_backend": "5001",
  "status": "success"
}
```

**Second Call (Routed to Backend 5002):**
```json
{
  "client_ip_seen": "127.0.0.1",
  "request_details": {
    "body": "",
    "headers": {
      "Accept": "*/*",
      "Accept-Encoding": "gzip, deflate",
      "Connection": "keep-alive",
      "Host": "127.0.0.1:5002",
      "User-Agent": "curl/8.5.0",
      "X-Forwarded-For": "127.0.0.1"
    },
    "method": "GET",
    "query_params": {},
    "url": "http://127.0.0.1:5002/"
  },
  "served_by_backend": "5002",
  "status": "success"
}
```

Notice how `served_by_backend` alternates on every request while `X-Forwarded-For` accurately presents the client socket IP.
