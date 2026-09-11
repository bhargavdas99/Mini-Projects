# this is the dummy backend script
# this will act as our dummy servers for this project

import sys
from flask import Flask, jsonify, request

app = Flask(__name__)
PORT = sys.argv[1] if len(sys.argv) > 1 else 5001


@app.route("/", methods=["GET", "POST", "PUT", "DELETE"])
def home():
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # Extract raw request payload (text/json/bytes)
    raw_body = request.get_data(as_text=True)

    return jsonify(
        {
            "status": "success",
            "served_by_backend": PORT,
            "client_ip_seen": client_ip,
            "request_details": {
                "method": request.method,
                "url": request.url,
                "headers": dict(request.headers),  # Converts headers to JSON dict
                "query_params": dict(request.args),  # E.g., ?search=foo
                "body": raw_body,  # Raw request payload
            },
        }
    )


if __name__ == "__main__":
    app.run(port=int(PORT))
