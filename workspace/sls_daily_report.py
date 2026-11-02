#!/usr/bin/env python3
"""
Daily SLS Error Log Analysis — leap-online / ling-server
Compares yesterday vs day-before-yesterday.
Daemon restart pattern for SLS API access.
"""
import sys, os, json, time
from datetime import datetime, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

# ── CONSTANTS ──────────────────────────────────────────────────────────────
AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Time calculation
now = datetime.now()
yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

YEST_FROM = str(int(yesterday_start.timestamp()))
YEST_TO = str(int(yesterday_end.timestamp()))
BEFORE_FROM = str(int(day_before_start.timestamp()))
BEFORE_TO = str(int(day_before_end.timestamp()))

YEST_DATE = yesterday_start.strftime("%Y-%m-%d")
BEFORE_DATE = day_before_start.strftime("%Y-%m-%d")
QUERY = "level: ERROR"

print(f"Yesterday: {YEST_DATE}  from={YEST_FROM} to={YEST_TO}")
print(f"DayBefore: {BEFORE_DATE} from={BEFORE_FROM} to={BEFORE_TO}")

# ── Daemon restart ──────────────────────────────────────────────────────
client = DaemonClient()
print("Killing existing daemon...")
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(2)
print("Starting fresh daemon...")
client.ensure_daemon_running()
time.sleep(2)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Registration: {resp}")
assert resp.get("status") == "success", f"Failed to register: {resp}"

# ── SLS API helper ──────────────────────────────────────────────────────
def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def safe_list(data):
    if isinstance(data, list):
        return data
    return []

def safe_sum_buckets(data):
    if isinstance(data, list):
        return sum(b.get("count", 0) for b in data)
    return 0

# ═══════════════════════════════════════════════════════════════════════
# STEP 1: Histograms for both days
# ═══════════════════════════════════════════════════════════════════════
print("\n=== Histogram: Yesterday ===")
yest_hist = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": QUERY, "from": YEST_FROM, "to": YEST_TO,
})
yest_total = safe_sum_buckets(yest_hist)
print(f"  Total: {yest_total}, Buckets: {len(safe_list(yest_hist))}")

print("\n=== Histogram: Day Before ===")
before_hist = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": QUERY, "from": BEFORE_FROM, "to": BEFORE_TO,
})
before_total = safe_sum_buckets(before_hist)
print(f"  Total: {before_total}, Buckets: {len(safe_list(before_hist))}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 2: Hourly distribution via SQL for both days
# ═══════════════════════════════════════════════════════════════════════
print("\n=== Hourly: Yesterday ===")
yest_hourly = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": YEST_FROM, "to": YEST_TO, "line": "50", "region": REGION,
})
print(f"  Hours: {len(safe_list(yest_hourly))}")

print("\n=== Hourly: Day Before ===")
before_hourly = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": BEFORE_FROM, "to": BEFORE_TO, "line": "50", "region": REGION,
})
print(f"  Hours: {len(safe_list(before_hourly))}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 3: Top error loggers via SQL for both days
# ═══════════════════════════════════════════════════════════════════════
print("\n=== Top Loggers: Yesterday ===")
yest_loggers = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": YEST_FROM, "to": YEST_TO, "line": "50", "region": REGION,
})
if isinstance(yest_loggers, list):
    for l in yest_loggers[:5]:
        print(f"  {l.get('logger', '?')}: {l.get('cnt', 0)}")

print("\n=== Top Loggers: Day Before ===")
before_loggers = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": BEFORE_FROM, "to": BEFORE_TO, "line": "50", "region": REGION,
})
if isinstance(before_loggers, list):
    for l in before_loggers[:5]:
        print(f"  {l.get('logger', '?')}: {l.get('cnt', 0)}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 4: Top error messages via SQL for both days
# ═══════════════════════════════════════════════════════════════════════
print("\n=== Top Messages: Yesterday ===")
yest_msgs = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20",
    "from": YEST_FROM, "to": YEST_TO, "line": "50", "region": REGION,
})
if isinstance(yest_msgs, list):
    for m in yest_msgs[:5]:
        msg = m.get("msg_sample", "?")[:100]
        print(f"  [{m.get('cnt', 0)}x] {msg}")

print("\n=== Top Messages: Day Before ===")
before_msgs = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20",
    "from": BEFORE_FROM, "to": BEFORE_TO, "line": "50", "region": REGION,
})
if isinstance(before_msgs, list):
    for m in before_msgs[:5]:
        msg = m.get("msg_sample", "?")[:100]
        print(f"  [{m.get('cnt', 0)}x] {msg}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 5: Root logger analysis for both days
# ═══════════════════════════════════════════════════════════════════════
print("\n=== Root Logger Messages: Yesterday ===")
yest_root = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YEST_FROM, "to": YEST_TO, "line": "50", "region": REGION,
})
if isinstance(yest_root, list):
    for m in yest_root[:5]:
        msg = m.get("msg_sample", "?")[:100]
        print(f"  [{m.get('cnt', 0)}x] {msg}")

print("\n=== Root Logger Messages: Day Before ===")
before_root = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f"{QUERY} and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": BEFORE_FROM, "to": BEFORE_TO, "line": "50", "region": REGION,
})
if isinstance(before_root, list):
    for m in before_root[:5]:
        msg = m.get("msg_sample", "?")[:100]
        print(f"  [{m.get('cnt', 0)}x] {msg}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 6: Keyword classification via GetHistograms (both days)
# ═══════════════════════════════════════════════════════════════════════
keywords = [
    "Dify", "DataCard", "生成失败", "创建角色记录失败", "任务状态不正确",
    "角色不存在", "孩子不属于你", "Internal Server Error", "Exception in ASGI",
    "LingSmartClient", "获取用户能量", "WALLPAPER_ERROR",
]

print("\n=== Keyword Classification ===")
keyword_results = {}
for kw in keywords:
    q = f'{QUERY} and "{kw}"'
    y_h = call_sls("GetHistograms", {"project": PROJECT, "logstore": LOGSTORE, "query": q, "from": YEST_FROM, "to": YEST_TO})
    b_h = call_sls("GetHistograms", {"project": PROJECT, "logstore": LOGSTORE, "query": q, "from": BEFORE_FROM, "to": BEFORE_TO})
    y_cnt = safe_sum_buckets(y_h)
    b_cnt = safe_sum_buckets(b_h)
    keyword_results[kw] = {"yesterday": y_cnt, "before": b_cnt}
    if y_cnt > 0 or b_cnt > 0:
        print(f"  {kw}: yesterday={y_cnt}, before={b_cnt}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 7: Peak hour drill-down - get top 3 peak hours from yesterday
# ═══════════════════════════════════════════════════════════════════════
print("\n=== Peak Hour Drill-down ===")
hourly_map_yest = {}
for h in safe_list(yest_hourly):
    hour_str = h.get("hour", "")
    cnt = int(h.get("cnt", 0))
    if hour_str:
        hourly_map_yest[hour_str] = cnt

# Sort and get top 3
sorted_hours = sorted(hourly_map_yest.items(), key=lambda x: x[1], reverse=True)
peak_hours = sorted_hours[:3]
print(f"  Top 3 peak hours: {peak_hours}")

peak_drilldown = {}
for hour_str, cnt in peak_hours:
    # Convert hour string to timestamp range
    h_int = int(hour_str.split(":")[0])
    cst_date = yesterday_start + timedelta(hours=h_int)
    from_utc = int(cst_date.timestamp())
    to_utc = from_utc + 3600
    print(f"  Drilling {hour_str} (cnt={cnt})...")
    drill = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"{QUERY} | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
        "from": str(from_utc), "to": str(to_utc), "line": "50", "region": REGION,
    })
    peak_drilldown[hour_str] = drill
    if isinstance(drill, list):
        for d in drill[:3]:
            print(f"    {d.get('logger', '?')}: {d.get('cnt', 0)}")

# ═══════════════════════════════════════════════════════════════════════
# STEP 8: Save all data
# ═══════════════════════════════════════════════════════════════════════
output = {
    "yesterday_date": YEST_DATE,
    "before_date": BEFORE_DATE,
    "yest_total": yest_total,
    "before_total": before_total,
    "yest_hist": yest_hist,
    "before_hist": before_hist,
    "yest_hourly": yest_hourly,
    "before_hourly": before_hourly,
    "yest_loggers": yest_loggers,
    "before_loggers": before_loggers,
    "yest_msgs": yest_msgs,
    "before_msgs": before_msgs,
    "yest_root": yest_root,
    "before_root": before_root,
    "keyword_results": keyword_results,
    "peak_hours": peak_hours,
    "peak_drilldown": peak_drilldown,
}

out_path = f"/root/.hermes/workspace/sls_daily_{YEST_DATE}.json"
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)
print(f"\nAll data saved to: {out_path}")
print("\n=== DATA COLLECTION COMPLETE ===")
