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

## Optional AgentScope Studio

AgentScope Studio can be exposed under the same origin at `/agent-studio/`. It
is intentionally an optional deployment: without the configuration below, the
backend sends no traces and the frontend hides its Agent tracking entry.

Start the service from the project root:

```bash
docker compose -f deploy/agentscope-studio/docker-compose.yml up -d
docker compose -f deploy/agentscope-studio/docker-compose.yml ps
```

The Compose service listens only on `127.0.0.1:3000`. Include the location
blocks from `deploy/agentscope-studio/nginx.conf` inside the same HTTPS
`server` block as the frontend and `/ws` location, then validate and reload
Nginx:

```bash
sudo htpasswd -c /etc/nginx/.htpasswd-agent-studio <studio-user>
sudo nginx -t
sudo systemctl reload nginx
```

The Nginx configuration requires `ngx_http_sub_module`; confirm it is present
with `nginx -V 2>&1 | grep -- --with-http_sub_module`. It is pinned to
`@agentscope/studio@1.0.9`, whose UI assumes root-relative routes. Do not
upgrade the Studio package without first rechecking the rewrite rules in that
file.

The template enables Nginx Basic Auth for `/agent-studio/`, its tRPC API, and
its Socket.IO endpoint. Studio does not provide production-grade access
control, and stored traces can contain prompts, model responses, tool inputs,
tool outputs, and data passed to the agents. You may replace Basic Auth with
VPN, SSO, or an IP allowlist, but apply the replacement to all three locations
so the API and live trace stream cannot bypass it.

AI Investor uses Studio as a trace-only integration to keep concurrent analysis
sessions isolated. It does not install AgentScope's global Studio hooks, so a
Studio run is registered as complete immediately; inspect the run's traces for
the individual analysis steps.
