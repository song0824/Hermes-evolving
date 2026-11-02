#!/usr/bin/env python3
"""
Daily SLS Error Log Analysis — Dual-day comparison (yesterday vs day-before)
Runs via daemon restart workaround for SLS API access.
"""
import sys, os, json, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

# ── CONSTANTS ──────────────────────────────────────────────────────────────
AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# ── Time calculation (CST = UTC+8) ─────────────────────────────────────────
now = datetime.now()
# Yesterday CST
yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
# Day before yesterday CST
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

yesterday_from = str(int(yesterday_start.timestamp()))
yesterday_to = str(int(yesterday_end.timestamp()))
day_before_from = str(int(day_before_start.timestamp()))
day_before_to = str(int(day_before_end.timestamp()))

print(f"Yesterday: {yesterday_start} to {yesterday_end}")
print(f"  Timestamps: from={yesterday_from}, to={yesterday_to}")
print(f"Day before: {day_before_start} to {day_before_end}")
print(f"  Timestamps: from={day_before_from}, to={day_before_to}")

# ── Daemon restart ─────────────────────────────────────────────────────────
client = DaemonClient()

print("\nKilling existing daemon...")
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(2)

print("Starting fresh daemon...")
client.ensure_daemon_running()
time.sleep(2)

resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Registration: {resp}")
assert resp.get("status") == "success", f"Failed to register: {resp}"

# ── SLS API helper ─────────────────────────────────────────────────────────
def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def safe_sum(data):
    if isinstance(data, list):
        return sum(b.get("count", 0) for b in data)
    return 0

# ── 1. GetHistograms for both days ─────────────────────────────────────────
print("\n[1] GetHistograms (yesterday)...")
hist_y = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR", "from": yesterday_from, "to": yesterday_to,
})
total_y = safe_sum(hist_y)
print(f"  Total: {total_y}, Buckets: {len(hist_y) if isinstance(hist_y, list) else 0}")

print("\n[2] GetHistograms (day before)...")
hist_d = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR", "from": day_before_from, "to": day_before_to,
})
total_d = safe_sum(hist_d)
print(f"  Total: {total_d}, Buckets: {len(hist_d) if isinstance(hist_d, list) else 0}")

# ── 2. Hourly distribution (SQL) ──────────────────────────────────────────
print("\n[3] Hourly distribution (yesterday)...")
hourly_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": yesterday_from, "to": yesterday_to, "line": "50", "region": REGION,
})
if isinstance(hourly_y, list):
    print(f"  Got {len(hourly_y)} hours")
else:
    print(f"  SQL returned: {hourly_y}")
    # Fallback: aggregate from histograms
    hourly_y = []

print("\n[4] Hourly distribution (day before)...")
hourly_d = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": day_before_from, "to": day_before_to, "line": "50", "region": REGION,
})
if isinstance(hourly_d, list):
    print(f"  Got {len(hourly_d)} hours")
else:
    print(f"  SQL returned: {hourly_d}")
    hourly_d = []

# Fallback: aggregate histograms into hourly buckets
def histogram_to_hourly(hist):
    """Aggregate 30-min histogram buckets into hourly counts."""
    if not isinstance(hist, list):
        return {}
    hourly = {}
    for b in hist:
        ts = b.get("from", 0)
        cst = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
        hour_key = cst.strftime("%H:00")
        hourly[hour_key] = hourly.get(hour_key, 0) + b.get("count", 0)
    return hourly

if not hourly_y and isinstance(hist_y, list):
    print("  Fallback: aggregating histograms for yesterday")
    hourly_y = [{"hour": h, "cnt": c} for h, c in sorted(histogram_to_hourly(hist_y).items())]
if not hourly_d and isinstance(hist_d, list):
    print("  Fallback: aggregating histograms for day before")
    hourly_d = [{"hour": h, "cnt": c} for h, c in sorted(histogram_to_hourly(hist_d).items())]

# ── 3. Top loggers ────────────────────────────────────────────────────────
print("\n[5] Top loggers (yesterday)...")
loggers_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": yesterday_from, "to": yesterday_to, "line": "50", "region": REGION,
})

print("\n[6] Top loggers (day before)...")
loggers_d = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": day_before_from, "to": day_before_to, "line": "50", "region": REGION,
})

# ── 4. Top error messages ─────────────────────────────────────────────────
print("\n[7] Top error messages (yesterday)...")
msgs_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": yesterday_from, "to": yesterday_to, "line": "50", "region": REGION,
})

print("\n[8] Top error messages (day before)...")
msgs_d = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": day_before_from, "to": day_before_to, "line": "50", "region": REGION,
})

# ── 5. Keyword-based error classification (GetHistograms) ─────────────────
print("\n[9] Keyword classification (yesterday)...")
keywords = [
    ("Dify", "Dify中间件"),
    ("DataCard", "DataCard中间件"),
    ("Internal Server Error", "Internal Server Error"),
    ("Exception in ASGI", "ASGI异常"),
    ("角色不存在", "角色不存在"),
    ("孩子不属于你", "孩子不属于你"),
    ("生成失败", "生成失败"),
    ("图片未通过风控", "图片未通过风控"),
    ("NoneType", "NoneType.stream"),
    ("voip", "VOIP相关"),
    ("LingSmartClient", "LingSmartClient"),
    ("Coze", "Coze错误"),
    ("Duplicate entry", "Duplicate Entry"),
    ("系统又出走", "系统又出走"),
    ("Magic", "魔法施展中"),
    ("TaskConflict", "TaskConflict"),
]

kw_y = {}
for kw, label in keywords:
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and {kw}", "from": yesterday_from, "to": yesterday_to,
    })
    kw_y[label] = safe_sum(h)

kw_d = {}
for kw, label in keywords:
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and {kw}", "from": day_before_from, "to": day_before_to,
    })
    kw_d[label] = safe_sum(h)

# ── 6. Version info ───────────────────────────────────────────────────────
print("\n[10] Version info sampling...")
def ver_sample(from_ts, to_ts):
    """Sample image version from first few seconds of the day."""
    logs = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR", "from": from_ts, "to": str(int(from_ts) + 120),
        "line": "5", "region": REGION,
    })
    versions = set()
    if isinstance(logs, list):
        for log in logs:
            img = log.get("__tag__:_image_name_", "")
            if "production" in img:
                # Extract version tag
                parts = img.split(":")
                if len(parts) > 1:
                    versions.add(parts[-1])
    return versions if versions else {"unknown"}

ver_y = ver_sample(yesterday_from, yesterday_to)
ver_d = ver_sample(day_before_from, day_before_to)
print(f"  Yesterday version: {ver_y}")
print(f"  Day before version: {ver_d}")

# ── 7. Peak hour drill-down ───────────────────────────────────────────────
print("\n[11] Peak hour drill-down...")
def get_peak_hour(hourly_data):
    """Find the hour with most errors."""
    if not isinstance(hourly_data, list) or not hourly_data:
        return None, 0
    peak = max(hourly_data, key=lambda x: x.get("cnt", 0))
    return peak.get("hour"), peak.get("cnt", 0)

peak_h_y, peak_c_y = get_peak_hour(hourly_y)
peak_h_d, peak_c_d = get_peak_hour(hourly_d)
print(f"  Yesterday peak: {peak_h_y} ({peak_c_y} errors)")
print(f"  Day before peak: {peak_h_d} ({peak_c_d} errors)")

# Drill-down for peak hours
def cst_hour_to_utc_ts(cst_hour_str, base_date):
    """Convert CST hour string (e.g., '05:00') to UTC timestamp range."""
    cst_h = int(cst_hour_str.split(":")[0])
    utc_h = (cst_h - 8) % 24
    base = datetime(base_date.year, base_date.month, base_date.day)
    utc_start = base + timedelta(hours=utc_h)
    utc_end = utc_start + timedelta(hours=1) - timedelta(seconds=1)
    return int(utc_start.timestamp()), int(utc_end.timestamp())

drill_y = None
drill_d = None
if peak_h_y:
    pf, pt = cst_hour_to_utc_ts(peak_h_y, yesterday_start)
    print(f"\n  Drill-down yesterday peak ({peak_h_y} CST):")
    drill_y = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
        "from": str(pf), "to": str(pt), "line": "50", "region": REGION,
    })
    if isinstance(drill_y, list):
        for d in drill_y[:5]:
            print(f"    {d.get('logger', '?')}: {d.get('cnt', 0)}")

if peak_h_d:
    pf, pt = cst_hour_to_utc_ts(peak_h_d, day_before_start)
    print(f"\n  Drill-down day-before peak ({peak_h_d} CST):")
    drill_d = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
        "from": str(pf), "to": str(pt), "line": "50", "region": REGION,
    })
    if isinstance(drill_d, list):
        for d in drill_d[:5]:
            print(f"    {d.get('logger', '?')}: {d.get('cnt', 0)}")

# ── Save all data ──────────────────────────────────────────────────────────
output = {
    "date_yesterday": yesterday_start.strftime("%Y-%m-%d"),
    "date_day_before": day_before_start.strftime("%Y-%m-%d"),
    "total_yesterday": total_y,
    "total_day_before": total_d,
    "histogram_yesterday": hist_y if isinstance(hist_y, list) else [],
    "histogram_day_before": hist_d if isinstance(hist_d, list) else [],
    "hourly_yesterday": hourly_y if isinstance(hourly_y, list) else [],
    "hourly_day_before": hourly_d if isinstance(hourly_d, list) else [],
    "loggers_yesterday": loggers_y if isinstance(loggers_y, list) else [],
    "loggers_day_before": loggers_d if isinstance(loggers_d, list) else [],
    "messages_yesterday": msgs_y if isinstance(msgs_y, list) else [],
    "messages_day_before": msgs_d if isinstance(msgs_d, list) else [],
    "keywords_yesterday": kw_y,
    "keywords_day_before": kw_d,
    "version_yesterday": list(ver_y),
    "version_day_before": list(ver_d),
    "peak_hour_yesterday": {"hour": peak_h_y, "count": peak_c_y},
    "peak_hour_day_before": {"hour": peak_h_d, "count": peak_c_d},
    "drill_peak_yesterday": drill_y if isinstance(drill_y, list) else [],
    "drill_peak_day_before": drill_d if isinstance(drill_d, list) else [],
}

out_path = f"/root/.hermes/workspace/sls_daily_{yesterday_start.strftime('%Y-%m-%d')}.json"
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)
print(f"\n✅ All data saved to: {out_path}")
