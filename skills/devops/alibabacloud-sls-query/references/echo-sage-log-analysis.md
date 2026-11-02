# Echo-Sage (lingos-oline-echo-sage) Log Analysis

## Logstore Details

- **Project**: `leap-online`, region: `cn-shanghai`
- **Logstore**: `lingos-oline-echo-sage` (⚠️ **oline** not online)
- **Key fields**: `msg`, `content`, `path`, `method`, `requestBody`, `statusCode`, `chainId`, `level`, `time`
- **No `logger` index** — cannot GROUP BY logger in analytical SQL

## Service Types

### ASR (WebSocket connections)

| Pattern | Value |
|---|---|
| Path | `/ws/asr` |
| Method | `GET` |
| msg | `request` |
| 1 log = 1 unique connection | ✅ |

**Query**: `ws/asr` (keyword match on path field)

### TTS (HTTP requests)

| Pattern | Value |
|---|---|
| Path | `/tts` |
| Method | `POST` |
| msg | `request` (unique HTTP request) |
| msg | `TTS` (internal processing — ~2x request count) |

**Unique requests**: `tts and msg: request`
**All TTS logs** (incl. internal processing): `tts` — returns ~2x because each request generates: text log, request body log, audio length log, HTTP request log

### TTS Platform Identification

The `tts_agent` field is in `requestBody` JSON at:
```json
{
  "data": {
    "attributes": {
      "options": {
        "tts_agent": "sensenova_luka_child"
      }
    }
  }
}
```

**Known platforms** (6/3 data):
- `sensenova_luka_child` — ~79% (default/primary)
- `vocengine_zh_male_tiancaitongsheng_mars_bigtts` — ~8% (天才童声)
- `vocengine_S_zNn1VJnq1` — ~10% (自定义音色)
- `vocengine_zh_female_zhixingnvsheng_mars_bigtts` — ~6% (知性女声)

**⚠️ `requestBody` is NOT indexed** — analytical SQL GROUP BY fails. Must sample with `GetLogs` and parse client-side.

**⚠️ `sensenova` keyword appears in Authorization header** of ALL requests — do NOT use for platform filtering. Use `luka_child`, `tiancaitongsheng`, `zhixingnvsheng`, or `zNn1VJnq1` instead.

## QPS/RPM Benchmarks (5/18 - 6/3)

| Metric | ASR | TTS |
|---|---|---|
| Week avg QPS | ~1.5 | ~9 |
| Peak QPS | 128 (5/24) | 119 (6/3) |
| Peak RPM | 449 (5/24) | 2,168 (5/24) |
| Daily volume range | 35K - 286K | 198K - 1.7M |

**Traffic pattern**: Higher on weekends (5/30-31 peak), lower on weekdays (6/2-3 low).

## Sampling Strategy for Platform Distribution

```python
# Small windows to avoid GetLogs response truncation
for h in range(24):
    for m in range(0, 60, 5):  # 5-min windows
        wf = base_ts + h * 3600 + m * 60
        wt = wf + 300
        logs = call_sls("GetLogs", {
            "query": "tts", "from": str(wf), "to": str(wt),
            "line": "2",  # Keep response small
        })
        # Parse requestBody JSON client-side
```

Scale proportionally: `est_total = sample_count / total_sampled * actual_total`
