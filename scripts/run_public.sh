#!/usr/bin/env bash
set -euo pipefail

# Run the app locally and expose it with Cloudflare Tunnel if available.
# Requirements:
#  - Python deps installed (Flask)
#  - Optional: cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)

PORT=${PORT:-5000}
HOST=${HOST:-127.0.0.1}
export FLASK_APP=${FLASK_APP:-app.py}
export FLASK_DEBUG=${FLASK_DEBUG:-1}

# Prefer venv's flask if present
if [[ -x "./.venv/bin/flask" ]]; then
  FLASK_CMD="./.venv/bin/flask"
else
  FLASK_CMD="flask"
fi

echo "Starting Flask on http://${HOST}:${PORT} ..."
${FLASK_CMD} run --host "${HOST}" --port "${PORT}" &
FLASK_PID=$!

echo "Flask PID: ${FLASK_PID}"

cleanup() {
  echo "Shutting down..."
  kill ${FLASK_PID} 2>/dev/null || true
}
trap cleanup INT TERM EXIT

if command -v cloudflared >/dev/null 2>&1; then
  echo "Starting Cloudflare Tunnel..."
  echo "(Press Ctrl+C to stop)"
  cloudflared tunnel --url "http://${HOST}:${PORT}" --edge-ip-version auto --protocol http2 || true
else
  if command -v ngrok >/dev/null 2>&1; then
    echo "cloudflared not found; falling back to ngrok."
    echo "Starting ngrok... (Press Ctrl+C to stop)"
    ngrok http ${PORT} || true
  else
    echo "No tunnel tool found. Install one of these to get a public URL:"
    echo " - Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    echo " - ngrok: https://ngrok.com/download"
    echo "Meanwhile, the app is available on your LAN at http://${HOST}:${PORT}"
    wait ${FLASK_PID}
  fi
fi
