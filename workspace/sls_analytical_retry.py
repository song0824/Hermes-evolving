#!/usr/bin/env python3
"""SLS analytical queries retry with fresh daemon."""
import sys, os, json, time
from datetime import datetime, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

now = datetime.now()
yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

yesterday_from = str(int(yesterday_start.timestamp()))
yesterday_to = str(int(yesterday_end.timestamp()))
day_before_from = str(int(day_before_start.timestamp()))
day_before_to = str(int(day_before_end.timestamp()))

# ── Daemon restart ──────────────────────────────────────────────────────
client = DaemonClient()
print("Killing existing daemon...")
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1.5)
print("Starting fresh daemon...")
client.ensure_daemon_running()
time.sleep(1.5)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Registration: {resp}")
assert resp.get("status") == "success", f"Failed to register: {resp}"

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

results = {}

# ── Yesterday: Top loggers ──────────────────────────────────────────────
print("\n[1] Yesterday top loggers...")
yesterday_loggers = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": yesterday_from, "to": yesterday_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(yesterday_loggers)}")
if isinstance(yesterday_loggers, list):
    print(f"  Count: {len(yesterday_loggers)}")
    for i, l in enumerate(yesterday_loggers[:10], 1):
        print(f"  {i}. {l.get('logger', '?')}: {l.get('cnt', 0)}")
elif isinstance(yesterday_loggers, dict):
    print(f"  Keys: {list(yesterday_loggers.keys())}")
    if "_error" in yesterday_loggers:
        print(f"  Error: {yesterday_loggers['_error']}")
results["yesterday_loggers"] = yesterday_loggers

# ── Yesterday: Top messages ─────────────────────────────────────────────
print("\n[2] Yesterday top messages...")
yesterday_msgs = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": yesterday_from, "to": yesterday_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(yesterday_msgs)}")
if isinstance(yesterday_msgs, list):
    print(f"  Count: {len(yesterday_msgs)}")
    for i, m in enumerate(yesterday_msgs[:10], 1):
        msg = m.get("msg_sample", "?")[:100]
        print(f"  {i}. [{m.get('cnt', 0)}x] {msg}")
elif isinstance(yesterday_msgs, dict):
    print(f"  Keys: {list(yesterday_msgs.keys())}")
    if "_error" in yesterday_msgs:
        print(f"  Error: {yesterday_msgs['_error']}")
results["yesterday_msgs"] = yesterday_msgs

# ── Day-before: Top loggers ─────────────────────────────────────────────
print("\n[3] Day-before top loggers...")
day_before_loggers = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": day_before_from, "to": day_before_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(day_before_loggers)}")
if isinstance(day_before_loggers, list):
    print(f"  Count: {len(day_before_loggers)}")
    for i, l in enumerate(day_before_loggers[:10], 1):
        print(f"  {i}. {l.get('logger', '?')}: {l.get('cnt', 0)}")
elif isinstance(day_before_loggers, dict):
    print(f"  Keys: {list(day_before_loggers.keys())}")
    if "_error" in day_before_loggers:
        print(f"  Error: {day_before_loggers['_error']}")
results["day_before_loggers"] = day_before_loggers

# ── Day-before: Top messages ────────────────────────────────────────────
print("\n[4] Day-before top messages...")
day_before_msgs = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": day_before_from, "to": day_before_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(day_before_msgs)}")
if isinstance(day_before_msgs, list):
    print(f"  Count: {len(day_before_msgs)}")
    for i, m in enumerate(day_before_msgs[:10], 1):
        msg = m.get("msg_sample", "?")[:100]
        print(f"  {i}. [{m.get('cnt', 0)}x] {msg}")
elif isinstance(day_before_msgs, dict):
    print(f"  Keys: {list(day_before_msgs.keys())}")
    if "_error" in day_before_msgs:
        print(f"  Error: {day_before_msgs['_error']}")
results["day_before_msgs"] = day_before_msgs

# ── Yesterday hourly ────────────────────────────────────────────────────
print("\n[5] Yesterday hourly distribution...")
yesterday_hourly = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": yesterday_from, "to": yesterday_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(yesterday_hourly)}")
if isinstance(yesterday_hourly, list):
    print(f"  Count: {len(yesterday_hourly)}")
    for h in yesterday_hourly:
        print(f"  {h.get('hour', '?')}: {h.get('cnt', 0)}")
elif isinstance(yesterday_hourly, dict):
    print(f"  Keys: {list(yesterday_hourly.keys())}")
    if "_error" in yesterday_hourly:
        print(f"  Error: {yesterday_hourly['_error']}")
results["yesterday_hourly"] = yesterday_hourly

# ── Day-before hourly ───────────────────────────────────────────────────
print("\n[6] Day-before hourly distribution...")
day_before_hourly = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": day_before_from, "to": day_before_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(day_before_hourly)}")
if isinstance(day_before_hourly, list):
    print(f"  Count: {len(day_before_hourly)}")
    for h in day_before_hourly:
        print(f"  {h.get('hour', '?')}: {h.get('cnt', 0)}")
elif isinstance(day_before_hourly, dict):
    print(f"  Keys: {list(day_before_hourly.keys())}")
    if "_error" in day_before_hourly:
        print(f"  Error: {day_before_hourly['_error']}")
results["day_before_hourly"] = day_before_hourly

# ── Yesterday: Top exceptions ───────────────────────────────────────────
print("\n[7] Yesterday top exceptions...")
yesterday_exceptions = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(exception, 1, 200) as exc_sample GROUP BY exc_sample ORDER BY cnt DESC LIMIT 10",
    "from": yesterday_from, "to": yesterday_to,
    "line": "50", "region": REGION,
})
print(f"  Result type: {type(yesterday_exceptions)}")
if isinstance(yesterday_exceptions, list):
    print(f"  Count: {len(yesterday_exceptions)}")
    for i, e in enumerate(yesterday_exceptions[:10], 1):
        exc = e.get("exc_sample", "?")[:100]
        print(f"  {i}. [{e.get('cnt', 0)}x] {exc}")
elif isinstance(yesterday_exceptions, dict):
    print(f"  Keys: {list(yesterday_exceptions.keys())}")
    if "_error" in yesterday_exceptions:
        print(f"  Error: {yesterday_exceptions['_error']}")
results["yesterday_exceptions"] = yesterday_exceptions

# Save
with open("/root/.hermes/workspace/sls_analytical.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print("\nSaved to /root/.hermes/workspace/sls_analytical.json")
