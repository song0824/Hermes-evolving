# Hermes Agent Timeout Diagnosis

## Diagnostic Checklist

When investigating intermittent API timeouts, check these layers in order:

### 1. Gateway Logs
```bash
grep -i "timeout\|timed out\|502\|503" ~/.hermes/logs/gateway.log | tail -50
```
Look for: `Gateway drain timed out`, `Request timed out`, `HTTP ERROR 502/503`

### 2. Config Timeout Settings
```bash
cat ~/.hermes/config.yaml | grep -A5 "model:"
```
If no `timeout` is set under `model:`, the OpenAI SDK default applies (can be 10+ minutes). A custom `timeout: 300` (5 min) is recommended for production.

### 3. Retry Configuration
```yaml
agent:
  api_max_retries: 3        # Default; increase for flaky providers
```
Retry backoff is jittered exponential: ~5s → ~10s → ~20s (see `agent/retry_utils.py`).

### 4. Error Classification
`agent/error_classifier.py` classifies timeout errors as `FailoverReason.timeout` with `retryable=True`. It rebuilds the client and retries, but does NOT:
- Auto-compress context on timeout
- Fallback to another model/provider
- Detect server-side queueing vs network timeout

### 5. Provider-Specific Risks
- **Custom provider** (DashScope, etc.): Single API key, no credential pool rotation. If the key or endpoint is slow, there is no automatic fallback.
- **OpenRouter/Anthropic**: Have credential pool rotation and multi-provider failover.
- **Auxiliary tasks**: Use their own timeout chain (vision: 30s, compression: varies, title gen: 30s). See `agent/auxiliary_client.py`.

### 6. Network Layer
- httpx persistent connections can hang if the server silently drops the connection
- Check if `model.base_url` points through a proxy or VPN (adds latency)
- Alibaba Cloud (DashScope) regional differences: Beijing vs Singapore nodes have different latency profiles

### 7. Context Size Impact
Large sessions (100K+ tokens, 200+ messages) increase:
- Request serialization time
- Server-side parsing time
- Probability of mid-stream disconnect

## Key Files
- `agent/retry_utils.py` — jittered backoff logic
- `agent/error_classifier.py` — error taxonomy and recovery decisions
- `agent/auxiliary_client.py` — side-task client with its own timeouts
- `~/.hermes/logs/gateway.log` — runtime error log
- `~/.hermes/config.yaml` — model/agent timeout config

## Common Timeout Sources
| Source | Symptom | Fix |
|--------|---------|-----|
| DashScope queueing | Long delay then success | Add `timeout: 300` to model config |
| httpx stale connection | ReadTimeout on first retry | Client rebuilds automatically |
| 502/503 from provider | Gateway log shows HTTP 502 | Retry covers this; check provider status |
| Context overflow | Server disconnect + large session | Error classifier should compress |
| Custom provider single key | No fallback on slow key | Add fallback_providers or credential pool |
