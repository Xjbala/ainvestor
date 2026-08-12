# Production WebSocket reverse proxy

The frontend connects to `VITE_WS_URL`, for example:

```env
VITE_WS_URL=wss://invest.junerai.com/ws
```

The Python WebSocket gateway listens separately on `WS_PORT` (default `8765`). The HTTPS reverse proxy must forward `/ws` with an HTTP/1.1 upgrade:

```nginx
location /ws {
    proxy_pass http://127.0.0.1:8765;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600;
    proxy_send_timeout 3600;
}
```

After changing the proxy, reload it and restart the backend process. Verify the route before testing an analysis:

```bash
websocat wss://invest.junerai.com/ws
```

Then send a command such as:

```json
{"type":"command","event":"start_analysis","data":{"tickers":["603137"],"date":"2026-08-11"}}
```

The backend log should contain `start_analysis` and `WS event broadcast` entries. If the browser receives no `session_start`, inspect the proxy's `101 Switching Protocols` handshake and confirm the backend is listening on `127.0.0.1:8765`.
