#!/usr/bin/env python3
"""SLS daily error analysis for 2026-07-02 (yesterday) vs 2026-07-01 (day before)."""
import sys, os, json, time

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Time ranges (CST dates -> UTC timestamps)
YESTERDAY_FROM = 1782921600   # 2026-07-02 00:00:00 CST
YESTERDAY_TO = 1783007999     # 2026-07-02 23:59:59 CST
DAY_BEFORE_FROM = 1782835200  # 2026-07-01 00:00:00 CST
DAY_BEFORE_TO = 1782921599    # 2026-07-01 23:59:59 CST

client = DaemonClient()

# Step 1: Kill existing daemon and restart
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)
client.ensure_daemon_running()
time.sleep(1)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Register: {resp}")

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def sum_histogram(hist):
    """Sum counts from histogram buckets."""
    if isinstance(hist, list):
        return sum(int(b.get("count", 0)) for b in hist)
    return 0

results = {}

# ==================== 1. Total counts via GetHistograms ====================
print("\n=== GetHistograms: Yesterday ===")
hist_y = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": str(YESTERDAY_FROM), "to": str(YESTERDAY_TO),
})
total_yesterday = sum_histogram(hist_y) if isinstance(hist_y, list) else hist_y
print(f"Yesterday total: {total_yesterday}")
results['histogram_yesterday'] = hist_y

print("\n=== GetHistograms: Day Before ===")
hist_db = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": str(DAY_BEFORE_FROM), "to": str(DAY_BEFORE_TO),
})
total_day_before = sum_histogram(hist_db) if isinstance(hist_db, list) else hist_db
print(f"Day before total: {total_day_before}")
results['histogram_day_before'] = hist_db

# ==================== 2. Hourly distribution via SQL ====================
print("\n=== Hourly: Yesterday ===")
hourly_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": str(YESTERDAY_FROM), "to": str(YESTERDAY_TO),
    "line": "30",
})
print(f"Hourly entries: {len(hourly_y) if isinstance(hourly_y, list) else hourly_y}")
results['hourly_yesterday'] = hourly_y

print("\n=== Hourly: Day Before ===")
hourly_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": str(DAY_BEFORE_FROM), "to": str(DAY_BEFORE_TO),
    "line": "30",
})
print(f"Hourly entries: {len(hourly_db) if isinstance(hourly_db, list) else hourly_db}")
results['hourly_day_before'] = hourly_db

# ==================== 3. Top Loggers ====================
print("\n=== Top Loggers: Yesterday ===")
loggers_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": str(YESTERDAY_FROM), "to": str(YESTERDAY_TO),
    "line": "30",
})
print(f"Logger entries: {len(loggers_y) if isinstance(loggers_y, list) else loggers_y}")
results['loggers_yesterday'] = loggers_y

print("\n=== Top Loggers: Day Before ===")
loggers_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": str(DAY_BEFORE_FROM), "to": str(DAY_BEFORE_TO),
    "line": "30",
})
print(f"Logger entries: {len(loggers_db) if isinstance(loggers_db, list) else loggers_db}")
results['loggers_day_before'] = loggers_db

# ==================== 4. Top Error Messages ====================
print("\n=== Top Messages: Yesterday ===")
msgs_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": str(YESTERDAY_FROM), "to": str(YESTERDAY_TO),
    "line": "20",
})
print(f"Message entries: {len(msgs_y) if isinstance(msgs_y, list) else msgs_y}")
results['messages_yesterday'] = msgs_y

print("\n=== Top Messages: Day Before ===")
msgs_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": str(DAY_BEFORE_FROM), "to": str(DAY_BEFORE_TO),
    "line": "20",
})
print(f"Message entries: {len(msgs_db) if isinstance(msgs_db, list) else msgs_db}")
results['messages_day_before'] = msgs_db

# ==================== 5. Keyword classification (GetHistograms) ====================
keywords = {
    "Dify": "Dify中间件",
    "DataCard": "DataCard中间件",
    "生成失败": "任务生成失败",
    "创建角色记录失败": "创建角色记录失败",
    "任务状态不正确": "任务状态不正确",
    "角色不存在": "角色不存在",
    "Internal Server Error": "Internal Server Error",
    "Unhandled Internal Server Error": "Unhandled ISE",
    "Exception in ASGI": "ASGI异常",
    "WALLPAPER_ERROR": "WALLPAPER_ERROR",
    "获取用户能量": "获取用户能量失败",
    "图片未通过风控": "图片未通过风控",
}

print("\n=== Keyword Classification: Yesterday ===")
kw_y = {}
for kw, label in keywords.items():
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f'level: ERROR and "{kw}"',
        "from": str(YESTERDAY_FROM), "to": str(YESTERDAY_TO),
    })
    cnt = sum_histogram(h) if isinstance(h, list) else 0
    kw_y[label] = cnt
    print(f"  {label}: {cnt}")
results['keywords_yesterday'] = kw_y

print("\n=== Keyword Classification: Day Before ===")
kw_db = {}
for kw, label in keywords.items():
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f'level: ERROR and "{kw}"',
        "from": str(DAY_BEFORE_FROM), "to": str(DAY_BEFORE_TO),
    })
    cnt = sum_histogram(h) if isinstance(h, list) else 0
    kw_db[label] = cnt
    print(f"  {label}: {cnt}")
results['keywords_day_before'] = kw_db

# ==================== 6. Version tracking ====================
print("\n=== Version: Yesterday (first 60s) ===")
ver_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": str(YESTERDAY_FROM), "to": str(YESTERDAY_FROM + 60),
    "line": "5",
})
versions_y = set()
if isinstance(ver_y, list):
    for log in ver_y:
        v = log.get("__tag__:_image_name_", "unknown")
        if v and v != "unknown":
            versions_y.add(v.split(":")[-1] if ":" in v else v)
results['version_yesterday'] = list(versions_y) if versions_y else ["unknown"]
print(f"Versions: {results['version_yesterday']}")

print("\n=== Version: Day Before (first 60s) ===")
ver_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": str(DAY_BEFORE_FROM), "to": str(DAY_BEFORE_FROM + 60),
    "line": "5",
})
versions_db = set()
if isinstance(ver_db, list):
    for log in ver_db:
        v = log.get("__tag__:_image_name_", "unknown")
        if v and v != "unknown":
            versions_db.add(v.split(":")[-1] if ":" in v else v)
results['version_day_before'] = list(versions_db) if versions_db else ["unknown"]
print(f"Versions: {results['version_day_before']}")

# ==================== 7. Peak hour drill-down (top 3 hours yesterday) ====================
hourly_y_list = hourly_y if isinstance(hourly_y, list) else []
if hourly_y_list:
    # Sort by count descending to get top 3 hours
    sorted_hours = sorted(hourly_y_list, key=lambda x: int(x.get('cnt', 0)), reverse=True)[:3]
    print(f"\n=== Peak Hours Yesterday: {[(h.get('hour','?'), h.get('cnt','?')) for h in sorted_hours]} ===")
    
    drill_down = {}
    for h_entry in sorted_hours:
        hour_str = h_entry.get('hour', '')
        try:
            cst_hour = int(hour_str.split(':')[0])
        except:
            continue
        # Convert CST hour to UTC hour for query
        utc_hour = (cst_hour - 8) % 24
        base_utc = YESTERDAY_FROM  # This is 2026-07-02 00:00:00 CST = UTC ts
        # YESTERDAY_FROM is the UTC timestamp of 2026-07-02 00:00:00 CST
        # So to get the window for CST hour X: from = YESTERDAY_FROM + (X * 3600) - (8*3600) ... 
        # Actually, YESTERDAY_FROM = timestamp of 2026-07-02 00:00:00 CST
        # So CST hour X window: from = YESTERDAY_FROM + X*3600, to = YESTERDAY_FROM + (X+1)*3600 - 1
        # The __time__ in SLS is UTC, but the SQL query already added 28800
        # Since YESTERDAY_FROM IS the UTC ts for CST 00:00, CST hour X is at YESTERDAY_FROM + X*3600
        drill_from = YESTERDAY_FROM + cst_hour * 3600
        drill_to = drill_from + 3600 - 1
        
        dd = call_sls("GetLogs", {
            "project": PROJECT, "logstore": LOGSTORE,
            "query": f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
            "from": str(drill_from), "to": str(drill_to),
            "line": "15",
        })
        drill_down[hour_str] = dd
        print(f"  Hour {hour_str} (CST): {len(dd) if isinstance(dd, list) else dd} logger entries")
    results['drill_down'] = drill_down

# Save results
output_path = "/root/.hermes/workspace/sls_daily_2026-07-02.json"
with open(output_path, 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\nResults saved to {output_path}")
print("\n=== QUERY COMPLETE ===")
