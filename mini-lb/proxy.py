# This is our reverse proxy which is a layer 7 - load balancer

import itertools
from flask import Flask, request, Response
import requests

app = Flask(__name__)

# Backend server pool
BACKENDS = [
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002",
]  # it knows that these backend servers are available
backend_cycle = itertools.cycle(BACKENDS)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    # Round-Robin selection (L7 Routing)
    target_backend = next(backend_cycle)
    url = f"{target_backend}/{path}"

    # Forward headers & inject X-Forwarded-For (L7 header manipulation)
    headers = {key: value for key, value in request.headers if key.lower() != "host"}
    headers["X-Forwarded-For"] = request.remote_addr

    try:
        # Forward request to backend
        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
        )

        # Exclude hop-by-hop headers from proxy response
        excluded_headers = [
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        ]
        proxy_headers = [
            (name, value)
            for (name, value) in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]

        return Response(resp.content, resp.status_code, proxy_headers)

    except requests.exceptions.RequestException as e:
        return Response(f"Backend Error: {str(e)}", status=502)


if __name__ == "__main__":
    app.run(port=8080)
