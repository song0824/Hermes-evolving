#!/usr/bin/env python3
"""Get error message samples via GetLogs for classification."""
import sys, os, json, time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

yesterday_from = "1784304000"
yesterday_to = "1784390399"
day_before_from = "1784217600"
day_before_to = "1784303999"

# ── Daemon setup ──
client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1.5)
client.ensure_daemon_running()
time.sleep(1.5)
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

def get_logs(query, from_ts, to_ts, line="20"):
    return call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
        "line": line, "region": REGION,
    })

# ── Get samples from multiple time windows ──
# Peak: 18:00-19:00 CST = 10:00-11:00 UTC
samples = {}

for name, f, t in [
    ("peak_18", "1784340000", "1784343599"),
    ("peak_13", "1784334600", "1784338199"),
    ("early_00", "1784304000", "1784307599"),
    ("night_21", "1784361600", "1784365199"),
    ("db_peak_13", "1784255400", "1784258999"),
    ("db_peak_10", "1784248200", "1784251799"),
]:
    logs = get_logs("level: ERROR", f, t, line="10")
    if isinstance(logs, list) and len(logs) > 0:
        samples[name] = logs
        print(f"\n=== {name} ({len(logs)} samples) ===")
        for log in logs[:8]:
            logger = log.get("logger", "N/A")
            message = log.get("message", "N/A")[:200]
            exc = log.get("exception", "")[:100]
            ts = log.get("__time__", "")
            if ts:
                cst = datetime.fromtimestamp(int(ts), tz=timezone(timedelta(hours=8))).strftime("%H:%M:%S")
            else:
                cst = "?"
            print(f"  [{cst}] logger={logger}")
            print(f"    msg={message}")
            if exc:
                print(f"    exc={exc}")
            print()
    else:
        print(f"\n=== {name} ===: no samples")

# ── Also try analytical SQL for message grouping on narrow windows ──
print("\n=== SQL: Yesterday message grouping (peak 18:00-19:00 CST) ===")
sql_result = get_logs("level: ERROR | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15", "1784340000", "1784343599")
if isinstance(sql_result, list) and len(sql_result) > 0:
    for r in sql_result[:15]:
        print(f"  cnt={r.get('cnt', '?')} msg={str(r.get('msg_sample', ''))[:120]}")
else:
    print("  (empty)")

print("\n=== SQL: Yesterday message grouping (full day, peak hour only) ===")
sql_result2 = get_logs("level: ERROR | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15", "1784334600", "1784343599")
if isinstance(sql_result2, list) and len(sql_result2) > 0:
    for r in sql_result2[:15]:
        print(f"  cnt={r.get('cnt', '?')} msg={str(r.get('msg_sample', ''))[:120]}")
else:
    print("  (empty)")

# SQL for day-before peak
print("\n=== SQL: Day-before message grouping (peak 13:00-14:00 CST) ===")
sql_result3 = get_logs("level: ERROR | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15", "1784255400", "1784258999")
if isinstance(sql_result3, list) and len(sql_result3) > 0:
    for r in sql_result3[:15]:
        print(f"  cnt={r.get('cnt', '?')} msg={str(r.get('msg_sample', ''))[:120]}")
else:
    print("  (empty)")

# Logger distribution in peak hours via SQL
print("\n=== SQL: Yesterday peak hour (18:00 CST) logger distribution ===")
logger_result = get_logs("level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10", "1784340000", "1784343599")
if isinstance(logger_result, list) and len(logger_result) > 0:
    for r in logger_result[:10]:
        print(f"  cnt={r.get('cnt', '?')} logger={r.get('logger', 'N/A')}")
else:
    print("  (empty)")

print("\n=== SQL: Day-before peak hour (13:00 CST) logger distribution ===")
logger_result2 = get_logs("level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10", "1784255400", "1784258999")
if isinstance(logger_result2, list) and len(logger_result2) > 0:
    for r in logger_result2[:10]:
        print(f"  cnt={r.get('cnt', '?')} logger={r.get('logger', 'N/A')}")
else:
    print("  (empty)")

print("\nDONE")
