#!/bin/sh
# Start the anime list and open it in the browser.
cd "$(dirname "$0")" || exit 1
(sleep 1 && xdg-open http://127.0.0.1:8765 >/dev/null 2>&1) &
exec python3 server.py 8765
