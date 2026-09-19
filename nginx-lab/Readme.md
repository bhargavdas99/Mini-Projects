
# Hands-On Nginx Architecture Lab: From Static Server to Resilient Reverse Proxy

A practical exploration of Nginx internals, network layers, and edge routing using Docker and Docker Compose.

---

## Project Overview

The objective was to demystify Nginx by building up its configuration step-by-step—progressing from basic file delivery to a production-ready Layer 7 reverse proxy, round-robin load balancer, and traffic-policing rate limiter.

---

## Phase 1: Static File Server & Event Loop Architecture

### Problem Statement
How does Nginx boot, manage OS-level sockets, and map incoming client requests to local disk paths or inline string responses?

### Architecture & Mechanics
- **Layer Distinction**: The `events` block operates at **Layer 4 (Transport Layer)**, managing Linux event-driven socket multiplexers (`epoll`) and tracking file descriptors via `worker_connections`. The `http` block operates at **Layer 7 (Application Layer)**, parsing HTTP/1.1 headers, URIs, and status codes.
- **URI Mapping**: Uses prefix routing where physical disk lookups follow `root + request_uri`.
- **MIME Parsing**: Uses `mime.types` hash map lookups to set accurate `Content-Type` headers for web assets.

### Solution Configuration (`Phase 1`)
```nginx
events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    server {
        listen 80;
        server_name localhost;

        location / {
            root /usr/share/nginx/html;
            index index.html;
        }

        location /ping {
            return 200 'pong\n';
            add_header Content-Type text/plain;
        }
    }
}

```

---

## Phase 2: Reverse Proxy & Context Preservation

### Problem Statement

Backend services typically run on internal application runtimes (Node, Python, Go) without public ports. How can Nginx sit in front to bridge external client traffic into private networks without dropping critical client metadata (IP address, requested domain, protocol scheme)?

### Architecture & Mechanics

* **The 2-Socket Rule**: Reverse proxying requires 2 active TCP sockets per request (Client $\leftrightarrow$ Nginx, and Nginx $\leftrightarrow$ Upstream). A pool of 1,024 connections supports $\approx 512$ concurrent proxied clients.
* **Service Discovery**: Docker's embedded DNS engine (`127.0.0.11`) dynamically resolves backend container names (`http://app1:5678`) across a shared bridge network.
* **Header Reconstruction**:
* `Host $host`: Preserves the domain requested by the client for downstream redirects.
* `X-Real-IP $remote_addr`: Stores the immediate caller's physical IP.
* `X-Forwarded-For $proxy_add_x_forwarded_for`: Maintains an append-only chain of proxy hops for audit logs.
* `X-Forwarded-Proto $scheme`: Informs backends whether TLS/HTTPS was terminated upstream.



### Solution Configuration (`Phase 2`)

```nginx
location /api/ {
    proxy_pass http://app1:5678/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

```

---

## Phase 3: Upstream Clustering & Load Balancing

### Problem Statement

A single backend instance presents a single point of failure and bottleneck. How do we distribute incoming traffic across an elastic cluster of backend replicas while abstracting internal container topology away from clients?

### Architecture & Mechanics

* **Round-Robin Scheduling**: Requests alternate deterministically across upstream nodes using an in-memory ring buffer.
* **Passive Health Checking**: Automatically marks instances down if connection attempts fail (`max_fails`, `fail_timeout`), immediately failing over to healthy nodes without returning 502/504 errors to end clients.

### Solution Configuration (`Phase 3`)

```nginx
http {
    upstream backend_cluster {
        server app1:5678;
        server app2:5678;
    }

    server {
        listen 80;
        server_name localhost;

        location /api/ {
            proxy_pass http://backend_cluster/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}

```

---

## Phase 4: Traffic Shaping & Rate Limiting

### Problem Statement

How do we protect backend pools from API abuse, brute-force requests, and denial-of-service spikes while accommodating legitimate traffic bursts?

### Architecture & Mechanics

* **Leaky Bucket Algorithm**: Enforces a continuous, fixed departure rate (`rate=2r/s`), smoothing spike patterns.
* **Memory Efficiency**: Tracks client IP addresses using `$binary_remote_addr` (4 bytes per IPv4 instead of 7–15 bytes in ASCII), allowing a 10MB zone to maintain state for $\approx 160{,}000$ unique IP addresses.
* **Burst Buffer with `nodelay**`: Buffers sudden spikes up to `burst=3` immediately without artificially sleeping connections, returning HTTP `429 Too Many Requests` as soon as the capacity threshold is breached.

### Solution Configuration (`Phase 4`)

```nginx
http {
    # 10MB shared memory zone tracking clients at 2 requests/sec
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=2r/s;
    limit_req_status 429;

    upstream backend_cluster {
        server app1:5678;
        server app2:5678;
    }

    server {
        listen 80;
        server_name localhost;

        location /api/ {
            limit_req zone=api_limit burst=3 nodelay;

            proxy_pass http://backend_cluster/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}

```

---

## Verification & Testing Guide

1. **Static & Inline Routes**:
```bash
curl http://localhost:8080/
curl http://localhost:8080/ping

```


2. **Load Balancer Alternation**:
```bash
for i in {1..4}; do curl http://localhost:8080/api/; done

```


*Expected Output: Alternating responses from `App 1` and `App 2`.*
3. **Rate Limiting Enforcement**:
```bash
for i in {1..8}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/; done

```


*Expected Output: Four `200` statuses followed by four `429` rate-limit rejections.*