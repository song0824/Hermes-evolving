#!/usr/bin/env python3
"""Daily SLS Error Analysis — 2026-10-07 vs 2026-10-06"""
import sys, os, json, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Time calculation (UTC-based, matching server timezone)
now = datetime.now()
yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

yesterday_from = str(int(yesterday_start.timestamp()))
yesterday_to = str(int(yesterday_end.timestamp()))
day_before_from = str(int(day_before_start.timestamp()))
day_before_to = str(int(day_before_end.timestamp()))

yesterday_date = yesterday_start.strftime("%Y-%m-%d")
day_before_date = day_before_start.strftime("%Y-%m-%d")

print(f"昨天: {yesterday_date} from={yesterday_from} to={yesterday_to}")
print(f"前天: {day_before_date} from={day_before_from} to={day_before_to}")

# Daemon restart
client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)
client.ensure_daemon_running()
time.sleep(1)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Registration: {resp.get('status')}")
assert resp.get("status") == "success", f"Register failed: {resp}"

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

# ── 1. GetHistograms for both days ──
print("\n[1] GetHistograms yesterday...")
hist_y = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR", "from": yesterday_from, "to": yesterday_to,
})
total_y = sum(b.get("count", 0) for b in hist_y) if isinstance(hist_y, list) else 0
print(f"  Total: {total_y}, Buckets: {len(hist_y) if isinstance(hist_y, list) else 0}")
results["hist_yesterday"] = hist_y
results["total_yesterday"] = total_y

print("[1b] GetHistograms day_before...")
hist_db = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR", "from": day_before_from, "to": day_before_to,
})
total_db = sum(b.get("count", 0) for b in hist_db) if isinstance(hist_db, list) else 0
print(f"  Total: {total_db}, Buckets: {len(hist_db) if isinstance(hist_db, list) else 0}")
results["hist_day_before"] = hist_db
results["total_day_before"] = total_db

# ── 2. Hourly distribution (SQL) for both days ──
print("\n[2] Hourly yesterday...")
hourly_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": yesterday_from, "to": yesterday_to, "line": "50", "region": REGION,
})
if not isinstance(hourly_y, list) or len(hourly_y) == 0:
    print("  SQL returned empty, falling back to histogram aggregation...")
    hourly_y = []
    if isinstance(hist_y, list):
        from datetime import timezone as tz, timedelta as td
        cst = tz(td(hours=8))
        hourly_map = {}
        for b in hist_y:
            ts = b.get("from", 0)
            hour = datetime.fromtimestamp(ts, tz=cst).strftime("%H:00")
            hourly_map[hour] = hourly_map.get(hour, 0) + b.get("count", 0)
        hourly_y = [{"hour": h, "cnt": c} for h, c in sorted(hourly_map.items())]
    results["hourly_yesterday_fallback"] = True
print(f"  Hours: {len(hourly_y)}")
results["hourly_yesterday"] = hourly_y

print("[2b] Hourly day_before...")
hourly_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": day_before_from, "to": day_before_to, "line": "50", "region": REGION,
})
if not isinstance(hourly_db, list) or len(hourly_db) == 0:
    print("  SQL returned empty, falling back to histogram aggregation...")
    hourly_db = []
    if isinstance(hist_db, list):
        from datetime import timezone as tz, timedelta as td
        cst = tz(td(hours=8))
        hourly_map = {}
        for b in hist_db:
            ts = b.get("from", 0)
            hour = datetime.fromtimestamp(ts, tz=cst).strftime("%H:00")
            hourly_map[hour] = hourly_map.get(hour, 0) + b.get("count", 0)
        hourly_db = [{"hour": h, "cnt": c} for h, c in sorted(hourly_map.items())]
    results["hourly_day_before_fallback"] = True
print(f"  Hours: {len(hourly_db)}")
results["hourly_day_before"] = hourly_db

# ── 3. Top loggers for both days ──
print("\n[3] Top loggers yesterday...")
loggers_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": yesterday_from, "to": yesterday_to, "line": "50", "region": REGION,
})
results["loggers_yesterday"] = loggers_y
if isinstance(loggers_y, list):
    print(f"  Loggers: {len(loggers_y)}")
    for l in loggers_y[:5]:
        print(f"    {l.get('logger','?')}: {l.get('cnt',0)}")
else:
    print(f"  Result: {loggers_y}")

print("[3b] Top loggers day_before...")
loggers_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": day_before_from, "to": day_before_to, "line": "50", "region": REGION,
})
results["loggers_day_before"] = loggers_db
if isinstance(loggers_db, list):
    print(f"  Loggers: {len(loggers_db)}")
    for l in loggers_db[:5]:
        print(f"    {l.get('logger','?')}: {l.get('cnt',0)}")
else:
    print(f"  Result: {loggers_db}")

# ── 4. Top error messages for both days ──
print("\n[4] Top messages yesterday...")
msgs_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": yesterday_from, "to": yesterday_to, "line": "50", "region": REGION,
})
results["messages_yesterday"] = msgs_y
if isinstance(msgs_y, list):
    print(f"  Messages: {len(msgs_y)}")
    for m in msgs_y[:5]:
        print(f"    [{m.get('cnt',0)}x] {m.get('msg_sample','?')[:80]}")
else:
    print(f"  Result: {msgs_y}")

print("[4b] Top messages day_before...")
msgs_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": day_before_from, "to": day_before_to, "line": "50", "region": REGION,
})
results["messages_day_before"] = msgs_db
if isinstance(msgs_db, list):
    print(f"  Messages: {len(msgs_db)}")
    for m in msgs_db[:5]:
        print(f"    [{m.get('cnt',0)}x] {m.get('msg_sample','?')[:80]}")
else:
    print(f"  Result: {msgs_db}")

# ── 5. Keyword-based category counts (GetHistograms) for both days ──
keywords = ["Dify", "DataCard", "LingSmartClient", "NoneType", "voip", "角色不存在", "生成失败", "图片未通过风控", "系统又出走", "TaskConflict", "Duplicate entry", "utf-8", "surrogate", "创作记录不存在", "Coze", "resource_rec"]
for kw in keywords:
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and {kw}", "from": yesterday_from, "to": yesterday_to,
    })
    cnt_y = sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0
    
    h2 = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and {kw}", "from": day_before_from, "to": day_before_to,
    })
    cnt_db = sum(b.get("count", 0) for b in h2) if isinstance(h2, list) else 0
    
    results.setdefault("keywords_yesterday", {})[kw] = cnt_y
    results.setdefault("keywords_day_before", {})[kw] = cnt_db

# ── 6. Version info (sample) ──
print("\n[6] Version info...")
ver_sample = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": yesterday_from, "to": str(int(yesterday_from) + 60), "line": "5", "region": REGION,
})
versions = set()
if isinstance(ver_sample, list):
    for log in ver_sample:
        v = log.get("__tag__:_image_name_", "")
        if v:
            versions.add(v.split(":")[-1] if ":" in v else v)
results["versions_yesterday"] = list(versions) if versions else ["unknown"]
print(f"  Versions: {results['versions_yesterday']}")

# ── Save ──
out_path = f"/root/.hermes/workspace/sls_daily_{yesterday_date}.json"
results["date"] = yesterday_date
results["day_before_date"] = day_before_date
with open(out_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\nAll results saved to: {out_path}")
print("DONE")
