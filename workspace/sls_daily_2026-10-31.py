#!/usr/bin/env python3
"""SLS daily error analysis for ling-server: 2026-10-31 vs 2026-10-30"""
import sys, os, json, time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Time: yesterday = 2026-10-31, day before = 2026-10-30 (CST)
cst = timezone(timedelta(hours=8))
yesterday_start = datetime(2026, 10, 31, 0, 0, 0, tzinfo=cst)
yesterday_end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=cst)
day_before_start = datetime(2026, 10, 30, 0, 0, 0, tzinfo=cst)
day_before_end = datetime(2026, 10, 30, 23, 59, 59, tzinfo=cst)

Y_FROM = str(int(yesterday_start.timestamp()))
Y_TO = str(int(yesterday_end.timestamp()))
D_FROM = str(int(day_before_start.timestamp()))
D_TO = str(int(day_before_end.timestamp()))

print(f"Yesterday (CST): 2026-10-31 00:00:00 to 2026-10-31 23:59:59")
print(f"Day before (CST): 2026-10-30 00:00:00 to 2026-10-30 23:59:59")
print(f"Yesterday ts: from={Y_FROM}, to={Y_TO}")
print(f"Day before ts: from={D_FROM}, to={D_TO}")

# Daemon restart
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)

client = DaemonClient()
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

# ========================================
# 1. GetHistograms for both days
# ========================================
print("\n=== GetHistograms: Yesterday ===")
y_hist = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": Y_FROM, "to": Y_TO,
})
print(f"Yesterday histogram buckets: {len(y_hist) if isinstance(y_hist, list) else y_hist}")

print("\n=== GetHistograms: Day Before ===")
d_hist = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": D_FROM, "to": D_TO,
})
print(f"Day before histogram buckets: {len(d_hist) if isinstance(d_hist, list) else d_hist}")

# Calculate totals
y_total = sum(b.get("count", 0) for b in (y_hist if isinstance(y_hist, list) else []))
d_total = sum(b.get("count", 0) for b in (d_hist if isinstance(d_hist, list) else []))
print(f"Yesterday total (histogram): {y_total}")
print(f"Day before total (histogram): {d_total}")

# ========================================
# 2. SQL: Hourly distribution for both days
# ========================================
print("\n=== SQL Hourly: Yesterday ===")
y_hourly = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": Y_FROM, "to": Y_TO, "line": "50",
})
if isinstance(y_hourly, list):
    print(f"Yesterday hourly entries: {len(y_hourly)}")
else:
    print(f"Yesterday hourly error: {y_hourly}")
    y_hourly = []

print("\n=== SQL Hourly: Day Before ===")
d_hourly = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": D_FROM, "to": D_TO, "line": "50",
})
if isinstance(d_hourly, list):
    print(f"Day before hourly entries: {len(d_hourly)}")
else:
    print(f"Day before hourly error: {d_hourly}")
    d_hourly = []

# Fallback: if SQL returns empty, aggregate from histogram
def agg_hourly_from_hist(buckets):
    hourly = {}
    for b in buckets:
        ts = int(b.get("from", 0))
        cst_dt = datetime.fromtimestamp(ts, tz=cst)
        hour_key = cst_dt.strftime("%H:00")
        hourly[hour_key] = hourly.get(hour_key, 0) + b.get("count", 0)
    return hourly

y_sql_hourly = {r.get("hour", ""): int(r.get("cnt", 0)) for r in y_hourly} if isinstance(y_hourly, list) else {}
d_sql_hourly = {r.get("hour", ""): int(r.get("cnt", 0)) for r in d_hourly} if isinstance(d_hourly, list) else {}

if not y_sql_hourly:
    print("SQL hourly empty for yesterday, falling back to histogram aggregation")
    y_sql_hourly = agg_hourly_from_hist(y_hist)
if not d_sql_hourly:
    print("SQL hourly empty for day before, falling back to histogram aggregation")
    d_sql_hourly = agg_hourly_from_hist(d_hist)

# ========================================
# 3. SQL: Top loggers for both days
# ========================================
print("\n=== SQL Top Loggers: Yesterday ===")
y_loggers = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": Y_FROM, "to": Y_TO, "line": "50",
})
y_logger_data = y_loggers if isinstance(y_loggers, list) else []
print(f"Yesterday logger entries: {len(y_logger_data)}")

print("\n=== SQL Top Loggers: Day Before ===")
d_loggers = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": D_FROM, "to": D_TO, "line": "50",
})
d_logger_data = d_loggers if isinstance(d_loggers, list) else []
print(f"Day before logger entries: {len(d_logger_data)}")

# ========================================
# 4. SQL: Top error messages for both days
# ========================================
print("\n=== SQL Top Messages: Yesterday ===")
y_messages = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": Y_FROM, "to": Y_TO, "line": "50",
})
y_msg_data = y_messages if isinstance(y_messages, list) else []
print(f"Yesterday message entries: {len(y_msg_data)}")

print("\n=== SQL Top Messages: Day Before ===")
d_messages = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": D_FROM, "to": D_TO, "line": "50",
})
d_msg_data = d_messages if isinstance(d_messages, list) else []
print(f"Day before message entries: {len(d_msg_data)}")

# ========================================
# 5. GetHistograms with keyword queries for error classification
# ========================================
keywords = [
    "3100", "NoneType", "Dify", "DataCard", "voip",
    "系统又出走", "TaskConflict", "Duplicate entry",
    "utf-8", "surrogate", "Coze", "创作记录不存在",
    "resource_rec", "already liked", "2001001175",
    "2001001338", "2001001325", "2001001324",
    "2001001321", "2001001347", "2001001312",
    "2001001307", "2001001301", "2001001304",
    "图片未通过风控", "生成失败", "创建角色记录失败",
    "任务状态不正确", "list index out of range",
    "WALLPAPER_ERROR", "获取用户能量失败",
]

y_keyword_counts = {}
d_keyword_counts = {}

for kw in keywords:
    yh = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and {kw}",
        "from": Y_FROM, "to": Y_TO,
    })
    dh = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and {kw}",
        "from": D_FROM, "to": D_TO,
    })
    y_count = sum(b.get("count", 0) for b in (yh if isinstance(yh, list) else []))
    d_count = sum(b.get("count", 0) for b in (dh if isinstance(dh, list) else []))
    if y_count > 0 or d_count > 0:
        y_keyword_counts[kw] = y_count
        d_keyword_counts[kw] = d_count
    time.sleep(0.1)

print(f"\nKeyword counts (yesterday): {y_keyword_counts}")
print(f"Keyword counts (day before): {d_keyword_counts}")

# ========================================
# 6. Version tracking (sample image names)
# ========================================
print("\n=== Version Tracking ===")
y_ver_sample = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": Y_FROM, "to": str(int(Y_FROM) + 3600),
    "line": "10",
})
d_ver_sample = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": D_FROM, "to": str(int(D_FROM) + 3600),
    "line": "10",
})

def extract_versions(logs):
    versions = set()
    if isinstance(logs, list):
        for log in logs:
            img = log.get("__tag__:_image_name_", "")
            if "production-" in img:
                parts = img.split(":")
                if len(parts) > 1:
                    tag = parts[-1]
                    versions.add(tag)
    return versions

y_versions = extract_versions(y_ver_sample)
d_versions = extract_versions(d_ver_sample)
print(f"Yesterday versions: {y_versions}")
print(f"Day before versions: {d_versions}")

# ========================================
# 7. Save data for report generation
# ========================================
result = {
    "date": "2026-10-31",
    "compare_date": "2026-10-30",
    "yesterday_total": y_total,
    "day_before_total": d_total,
    "yesterday_hourly": y_sql_hourly,
    "day_before_hourly": d_sql_hourly,
    "yesterday_loggers": y_logger_data,
    "day_before_loggers": d_logger_data,
    "yesterday_messages": y_msg_data,
    "day_before_messages": d_msg_data,
    "yesterday_keywords": y_keyword_counts,
    "day_before_keywords": d_keyword_counts,
    "yesterday_versions": list(y_versions),
    "day_before_versions": list(d_versions),
}

with open("/root/.hermes/workspace/sls_daily_2026-10-31.json", "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n=== Data saved to /root/.hermes/workspace/sls_daily_2026-10-31.json ===")
print(f"Yesterday total errors: {y_total}")
print(f"Day before total errors: {d_total}")
change = ((y_total - d_total) / d_total * 100) if d_total > 0 else 0
print(f"Change: {change:+.1f}%")
