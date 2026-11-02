#!/usr/bin/env python3
"""Drill-down queries for peak hours."""
import sys, os, json, time

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

client = DaemonClient()

# Kill old daemon and restart
print("Killing old daemon...")
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(2)
print("Starting fresh daemon...")
client.ensure_daemon_running()
time.sleep(2)

resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Registration: {resp}")

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

# 04:00-04:30 CST = 20:00-20:30 UTC on June 7
# from = 1780808400 (20:00 UTC), to = 1780810200 (20:30 UTC)
PEAK_FROM = "1780808400"
PEAK_TO = "1780810200"

print("\n=== Peak Window 04:00-04:30 CST: Top Loggers ===")
drill = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": PEAK_FROM, "to": PEAK_TO, "line": "50", "region": REGION,
})
if isinstance(drill, list):
    for d in drill:
        print(f"  {d.get('logger', '?')}: {d.get('cnt', 0)}")

print("\n=== Peak Window 04:00-04:30 CST: Top Messages ===")
msgs = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20",
    "from": PEAK_FROM, "to": PEAK_TO, "line": "50", "region": REGION,
})
if isinstance(msgs, list):
    for m in msgs:
        msg = m.get("msg_sample", "?")[:120]
        print(f"  [{m.get('cnt', 0)}x] {msg}")

# 05:00-05:30 CST = 21:00-21:30 UTC
PEAK2_FROM = "1780812000"
PEAK2_TO = "1780813800"

print("\n=== Peak Window 05:00-05:30 CST: Top Loggers ===")
drill2 = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": PEAK2_FROM, "to": PEAK2_TO, "line": "50", "region": REGION,
})
if isinstance(drill2, list):
    for d in drill2:
        print(f"  {d.get('logger', '?')}: {d.get('cnt', 0)}")

print("\n=== Peak Window 05:00-05:30 CST: Top Messages ===")
msgs2 = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20",
    "from": PEAK2_FROM, "to": PEAK2_TO, "line": "50", "region": REGION,
})
if isinstance(msgs2, list):
    for m in msgs2:
        msg = m.get("msg_sample", "?")[:120]
        print(f"  [{m.get('cnt', 0)}x] {msg}")

# Check Dify + DataCard breakdown in peak window
print("\n=== Peak Window: Dify vs DataCard Logger Distribution ===")
dify = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f'level: ERROR and "Dify" | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10',
    "from": PEAK_FROM, "to": PEAK_TO, "line": "50", "region": REGION,
})
if isinstance(dify, list):
    for d in dify:
        print(f"  [Dify] {d.get('logger', '?')}: {d.get('cnt', 0)}")

# Check exception_handlers breakdown
print("\n=== Peak Window: exception_handlers messages ===")
eh = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f'level: ERROR and logger: app.exception_handlers | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10',
    "from": PEAK_FROM, "to": PEAK_TO, "line": "50", "region": REGION,
})
if isinstance(eh, list):
    for e in eh:
        msg = e.get("msg_sample", "?")[:120]
        print(f"  [{e.get('cnt', 0)}x] {msg}")

# Check if there's a version change
print("\n=== Peak Window: Image versions ===")
# Cannot query __tag__ in SQL, so let's get raw samples
samples = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": PEAK_FROM, "to": PEAK_TO, "line": "3", "region": REGION,
})
if isinstance(samples, list):
    for s in samples:
        img = s.get("__tag__:_image_name_", "N/A")
        print(f"  Version: {img}")
        print(f"  Time: {s.get('__time__', '?')}")
        print(f"  Message: {s.get('message', '?')[:100]}")
        print()

print("\n=== DRILLDOWN COMPLETE ===")
