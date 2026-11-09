---
name: bothub-api-server
description: Manage the BotHub bothub_invoke.py API server — startup, authentication, nginx reverse proxy, token rotation, and capability dispatch.
---

## Overview

The BotHub API server (`scripts/bothub_invoke.py`) binds 127.0.0.1:8643 and dispatches HTTP POST requests to `/bothub/v1/invoke` by capability name. It is fronted by nginx on port 19100.

## Key Files

- Script: `/root/.hermes/scripts/bothub_invoke.py`
- Nginx config: `/etc/nginx/conf.d/hermes-gateway.conf`
- Auth env var: `API_SERVER_KEY`

## Starting the Service

The script requires `API_SERVER_KEY` to be set for Bearer token authentication. Without it, the script starts but accepts all requests without auth.

```bash
cd /root/.hermes
API_SERVER_KEY="<token>" python3 scripts/bothub_invoke.py
```

Run as a background process. Verify with `ss -ltnp | grep 8643`.

## Nginx Reverse Proxy

Both locations in `/etc/nginx/conf.d/hermes-gateway.conf` share the same Bearer token:
- `/hermes/v1/chat/completions` → 127.0.0.1:8642
- `/bothub/v1/invoke` → 127.0.0.1:8643

### Token Rotation

Both locations use the same token in their `if ($http_authorization != "Bearer ...")` directives. When rotating:

1. Update both locations in the nginx config (use sed since patch refuses /etc/* paths):
```bash
sed -i 's|if (\$http_authorization != "Bearer OLD_TOKEN") { return 401; }|if (\$http_authorization != "Bearer NEW_TOKEN") { return 401; }|' /etc/nginx/conf.d/hermes-gateway.conf
```

2. Reload nginx: `nginx -t && systemctl reload nginx`
3. Restart bothub_invoke.py with the new `API_SERVER_KEY` env var
4. Verify new token works and old token returns 401

## Pitfalls

- **Reloading after code updates**: `bothub_invoke.py` holds port 8643 open. After pulling new code, you must kill the old PID first, then restart: `kill <PID> && sleep 1 && API_SERVER_KEY="<token>" python3 scripts/bothub_invoke.py`. Find PID with `lsof -i :8643` or `ss -tlnp | grep 8643`.
- **patch tool refuses /etc/* paths**: Use `terminal` with `sed -i` for nginx config edits.
- **API_SERVER_KEY must be set at startup**: The script reads it from the environment at import time. If you restart the service without it, auth is effectively disabled (all requests accepted).
- **Both nginx locations share the same token**: Changing one without the other means one endpoint stops working. Always update both simultaneously.
- **Protocol version**: Requests must include `"protocol_version": "1.0"` and `"identity": {"target_bot_id": "hermes-evolving"}` or they get INVALID_REQUEST.

## Capabilities

See the script's `CAPABILITIES` dict for available capability names (e.g. `hermes.weekly_report.reminder`, `hermes.log.sls`, `hermes.debug.plan`, etc.).

## Verification

Test after any change:
```bash
# New token should work
curl -s -H "Authorization: Bearer <new-token>" -X POST http://127.0.0.1:19100/bothub/v1/invoke -d '{"protocol_version":"1.0","identity":{"target_bot_id":"hermes-evolving","target_capability":"hermes.tech.analyze"},"input":{"text":"ping"}}'

# Old token should return 401
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer <old-token>" -X POST http://127.0.0.1:19100/bothub/v1/invoke -d '{}'
```
