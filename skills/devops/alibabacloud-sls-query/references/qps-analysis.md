# SLS QPS Analysis Workflow

## Core Principle
QPS (Queries Per Second) = **number of log entries in a single second** from an access/request log.

## Standard SQL Template

```sql
<search_query> | SELECT count(1) as cnt, from_unixtime(__time__ + 28800) as time_sec GROUP BY from_unixtime(__time__ + 28800) ORDER BY cnt DESC LIMIT <N>
```

- `__time__`: SLS log timestamp in UNIX seconds (UTC)
- `+ 28800`: Convert to Beijing time (UTC+8)
- `from_unixtime()`: Group by exact second
- `ORDER BY cnt DESC LIMIT <N>`: Get top N peak seconds

## API Parameters
```json
{
  "project": "<project>",
  "logstore": "<logstore>",
  "query": "<search_query> | SELECT count(1) as cnt, from_unixtime(__time__ + 28800) as time_sec GROUP BY from_unixtime(__time__ + 28800) ORDER BY cnt DESC LIMIT 1",
  "from": "<start_unix_ts>",
  "to": "<end_unix_ts>",
  "line": "1",
  "powerSql": "true"
}
```

## Average QPS Formula
```
avg_qps = total_log_count / 86400
```
Where 86400 = seconds in a day.

## Important Notes

1. **Console chart sampling**: The SLS console's histogram/chart visualization applies sampling for large datasets. A chart tooltip showing `124` may correspond to `250` from SQL analysis. Always trust SQL results over chart numbers.

2. **Log-to-request ratio**: Each HTTP request may generate multiple log entries. For `uvicorn.access`, 1 request = 1 log entry. For business logs, a single request may generate 5+ entries (请求开始, HTTP请求, HTTP响应, etc.). Check the log pattern before equating log count to request count.

3. **`__tag__` filter limitation**: Do NOT include `__tag__:` filters in the query string — they cause SDK errors via API. Use keyword matching only, and parse tags from raw results if needed.

## ⚠️ GetLogs Response Size Pitfall (Critical for QPS)

**Analytical SQL QPS queries (`GROUP BY from_unixtime(__time__)`) can return massive responses** that exceed the tool's output limit, even with `line: 1`. This happens because:
- The `line` parameter limits rows returned, NOT response size
- A single row with a large timestamp string or aggregated data can still be huge
- **Solution**: Use `GetHistograms` for totals (30-min buckets, reliable), and `GetLogs` with analytical SQL only when the result set is small

**Verified pattern that works**: `GetLogs` with analytical QPS SQL + `line: 5` returns correctly. If it returns empty/0, the response is being truncated silently — reduce the time window.

## ⚠️ Extracting Platform/Vendor from Non-Indexed JSON Fields

**SLS analytical SQL cannot GROUP BY fields that are not in the index configuration.** The `requestBody` field in `lingos-oline-echo-sage` is NOT indexed, so:
- `| SELECT ..., regexp_extract(requestBody, 'tts_agent', 1)` → `Column 'requestbody' cannot be resolved`
- **Workaround**: Use `GetLogs` with small `line` values, parse `requestBody` JSON client-side with Python `json.loads()`, and aggregate in Python

**Sampling strategy for platform distribution**:
1. Split the day into small windows (e.g., 5-min or 10-min)
2. Query each window with `line: 2` (keep response small to avoid truncation)
3. Parse `requestBody` JSON → extract the target field
4. Scale counts proportionally: `est_total = sample_count / total_sampled * actual_total`
5. Use `GetHistograms` on the full day for `actual_total`

## ⚠️ Keyword-in-Shared-Field Pitfall

**A keyword may appear in multiple log fields, causing false matches.** Example: `sensenova` appears in the `Authorization` header signature of ALL TTS requests (regardless of actual platform), so `GetHistograms` with query `tts and sensenova` returns 100% of traffic.

**Rule**: When a keyword matches unexpectedly high volumes, check which field it appears in. Use `GetLogs` to inspect raw logs and identify the exact field containing the keyword. Prefer unique identifiers (e.g., `luka_child`, `tiancaitongsheng`) that only appear in the target field.

## Multi-day Comparison Script Pattern

```python
for day in range(start_day, end_day + 1):
    today_bj = datetime(2026, 5, day, 0, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    from_ts = int(today_bj.timestamp())
    to_ts = from_ts + 86400
    
    # Peak QPS
    logs = call_sls("GetLogs", {
        "query": "... | SELECT count(1) as cnt, from_unixtime(...) ... ORDER BY cnt DESC LIMIT 1",
        "from": str(from_ts), "to": str(to_ts),
        "line": "1", "powerSql": "true",
    })
    
    # Total for average
    logs_total = call_sls("GetLogs", {
        "query": "... | SELECT count(1) as total FROM log",
        "from": str(from_ts), "to": str(to_ts),
        "line": "1", "powerSql": "true",
    })
```
