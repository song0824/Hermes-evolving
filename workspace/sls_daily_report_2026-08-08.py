#!/usr/bin/env python3
"""
SLS Daily Error Report — Dual-Day Comparison (Yesterday vs Day Before)
Date: 2026-08-08 (yesterday) vs 2026-08-07 (day before)
"""
import sys, os, json, time, re
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

# ── CONSTANTS ──────────────────────────────────────────────────────────────
AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Time ranges (UTC timestamps for CST days)
# Yesterday: 2026-08-08 CST = UTC 2026-08-07 16:00 → 2026-08-08 16:00
cst = timezone(timedelta(hours=8))
yesterday_start = datetime(2026, 8, 8, 0, 0, 0, tzinfo=cst)
yesterday_end = datetime(2026, 8, 8, 23, 59, 59, tzinfo=cst)
day_before_start = datetime(2026, 8, 7, 0, 0, 0, tzinfo=cst)
day_before_end = datetime(2026, 8, 7, 23, 59, 59, tzinfo=cst)

Y_FROM = str(int(yesterday_start.timestamp()))
Y_TO = str(int(yesterday_end.timestamp()))
D_FROM = str(int(day_before_start.timestamp()))
D_TO = str(int(day_before_end.timestamp()))

print(f"Yesterday (2026-08-08): from={Y_FROM}, to={Y_TO}")
print(f"Day Before (2026-08-07): from={D_FROM}, to={D_TO}")

# ── Daemon restart ──────────────────────────────────────────────────────
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

# ── SLS API helper ──────────────────────────────────────────────────────
def call_sls(action, params):
    """Call SLS API. Returns the 'data' field from the response."""
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def get_histogram_total(query, from_ts, to_ts):
    """Get total error count from GetHistograms."""
    hist = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
    })
    if isinstance(hist, list):
        return sum(b.get("count", 0) for b in hist), hist
    return 0, hist

def get_logs_sql(query, from_ts, to_ts, line="50"):
    """Run analytical SQL query."""
    return call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query,
        "from": from_ts, "to": to_ts,
        "line": line, "region": REGION,
    })

# ═══════════════════════════════════════════════════════════
# STEP 1: Total error counts (GetHistograms)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1: Total Error Counts")
print("="*60)

y_total, y_hist = get_histogram_total("level: ERROR", Y_FROM, Y_TO)
d_total, d_hist = get_histogram_total("level: ERROR", D_FROM, D_TO)
print(f"Yesterday (08-08): {y_total} errors")
print(f"Day Before (08-07): {d_total} errors")

if d_total > 0:
    change_pct = (y_total - d_total) / d_total * 100
    print(f"Change: {change_pct:+.1f}%")

# ═══════════════════════════════════════════════════════════
# STEP 2: Hourly distribution (SQL GROUP BY hour)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 2: Hourly Distribution")
print("="*60)

y_hourly_raw = get_logs_sql(
    "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    Y_FROM, Y_TO, "50"
)
d_hourly_raw = get_logs_sql(
    "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    D_FROM, D_TO, "50"
)

y_hourly = {}
if isinstance(y_hourly_raw, list):
    for h in y_hourly_raw:
        y_hourly[h.get("hour", "")] = int(h.get("cnt", 0))
    print(f"Yesterday hours: {len(y_hourly_raw)} buckets")
else:
    print(f"Yesterday SQL result: {y_hourly_raw}")
    # Fallback: aggregate from histogram
    if isinstance(y_hist, list):
        for b in y_hist:
            hour = datetime.fromtimestamp(b["from"], tz=cst).strftime("%H:00")
            y_hourly[hour] = y_hourly.get(hour, 0) + b.get("count", 0)

d_hourly = {}
if isinstance(d_hourly_raw, list):
    for h in d_hourly_raw:
        d_hourly[h.get("hour", "")] = int(h.get("cnt", 0))
    print(f"Day Before hours: {len(d_hourly_raw)} buckets")
else:
    print(f"Day Before SQL result: {d_hourly_raw}")
    if isinstance(d_hist, list):
        for b in d_hist:
            hour = datetime.fromtimestamp(b["from"], tz=cst).strftime("%H:00")
            d_hourly[hour] = d_hourly.get(hour, 0) + b.get("count", 0)

# ═══════════════════════════════════════════════════════════
# STEP 3: Top loggers
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 3: Top Loggers")
print("="*60)

y_loggers_raw = get_logs_sql(
    "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    Y_FROM, Y_TO, "50"
)
d_loggers_raw = get_logs_sql(
    "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    D_FROM, D_TO, "50"
)

y_loggers = {}
if isinstance(y_loggers_raw, list):
    for l in y_loggers_raw:
        y_loggers[l.get("logger", "unknown")] = int(l.get("cnt", 0))
    print("Yesterday Top 10 loggers:")
    for l in sorted(y_loggers.items(), key=lambda x: -x[1])[:10]:
        print(f"  {l[0]}: {l[1]}")
else:
    print(f"Yesterday loggers result: {y_loggers_raw}")

d_loggers = {}
if isinstance(d_loggers_raw, list):
    for l in d_loggers_raw:
        d_loggers[l.get("logger", "unknown")] = int(l.get("cnt", 0))
    print("Day Before Top 10 loggers:")
    for l in sorted(d_loggers.items(), key=lambda x: -x[1])[:10]:
        print(f"  {l[0]}: {l[1]}")
else:
    print(f"Day Before loggers result: {d_loggers_raw}")

# ═══════════════════════════════════════════════════════════
# STEP 4: Top error messages
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 4: Top Error Messages")
print("="*60)

y_msgs_raw = get_logs_sql(
    "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    Y_FROM, Y_TO, "50"
)
d_msgs_raw = get_logs_sql(
    "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    D_FROM, D_TO, "50"
)

y_msgs = []
if isinstance(y_msgs_raw, list):
    for m in y_msgs_raw:
        y_msgs.append({"msg": m.get("msg_sample", "")[:150], "cnt": int(m.get("cnt", 0))})
    print("Yesterday Top 10 messages:")
    for m in y_msgs[:10]:
        print(f"  [{m['cnt']}x] {m['msg'][:100]}")
else:
    print(f"Yesterday messages result: {y_msgs_raw}")

d_msgs = []
if isinstance(d_msgs_raw, list):
    for m in d_msgs_raw:
        d_msgs.append({"msg": m.get("msg_sample", "")[:150], "cnt": int(m.get("cnt", 0))})
    print("Day Before Top 10 messages:")
    for m in d_msgs[:10]:
        print(f"  [{m['cnt']}x] {m['msg'][:100]}")
else:
    print(f"Day Before messages result: {d_msgs_raw}")

# ═══════════════════════════════════════════════════════════
# STEP 5: Keyword-based classification (GetHistograms)
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 5: Keyword Classification (GetHistograms)")
print("="*60)

keywords = [
    ("Dify", "Dify中间件异常"),
    ("DataCard", "DataCard中间件异常"),
    ("Unhandled Internal Server Error", "Unhandled ISE"),
    ("Internal Server Error", "Internal Server Error (含Unhandled)"),
    ("Exception in ASGI", "ASGI异常"),
    ("LingSmartClient", "ling-smart-svc连接问题"),
    ("角色不存在", "角色不存在(2001001175)"),
    ("生成失败", "任务生成失败"),
    ("图片未通过风控", "图片未通过风控"),
    ("WALLPAPER_ERROR", "WALLPAPER_ERROR"),
    ("获取用户能量", "获取用户能量失败"),
    ("已经点赞", "已经点赞"),
]

y_keywords = {}
d_keywords = {}

for kw, label in keywords:
    y_count, _ = get_histogram_total(f"level: ERROR and \"{kw}\"", Y_FROM, Y_TO)
    d_count, _ = get_histogram_total(f"level: ERROR and \"{kw}\"", D_FROM, D_TO)
    y_keywords[label] = y_count
    d_keywords[label] = d_count
    change = ""
    if d_count > 0:
        pct = (y_count - d_count) / d_count * 100
        change = f" ({pct:+.1f}%)"
    elif y_count > 0:
        change = " (NEW)"
    print(f"  {label}: Y={y_count}, D={d_count}{change}")

# ═══════════════════════════════════════════════════════════
# STEP 6: Peak hour drill-down
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 6: Peak Hour Drill-Down")
print("="*60)

def cst_hour_to_utc_from(cst_hour_str, base_date):
    """Convert CST hour string like '05:00' to UTC from_ts for that day."""
    cst_h = int(cst_hour_str.split(":")[0])
    utc_h = (cst_h - 8) % 24
    dt = datetime(base_date.year, base_date.month, base_date.day, utc_h, 0, 0, tzinfo=timezone.utc)
    return int(dt.timestamp())

# Find peak hours for yesterday
y_sorted_hours = sorted(y_hourly.items(), key=lambda x: -x[1])[:3]
print(f"Yesterday Top 3 peak hours: {y_sorted_hours}")

y_drilldowns = {}
for hour_str, count in y_sorted_hours:
    from_ts = cst_hour_to_utc_from(hour_str, yesterday_start)
    to_ts = from_ts + 3600
    drill = get_logs_sql(
        f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
        str(from_ts), str(to_ts), "30"
    )
    if isinstance(drill, list):
        y_drilldowns[hour_str] = {l.get("logger", "?"): int(l.get("cnt", 0)) for l in drill}
        print(f"  {hour_str} CST ({count} total):")
        for logger, cnt in sorted(y_drilldowns[hour_str].items(), key=lambda x: -x[1])[:5]:
            print(f"    {logger}: {cnt}")
    else:
        print(f"  {hour_str} CST: drill-down failed: {drill}")

# ═══════════════════════════════════════════════════════════
# STEP 7: Version tracking
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 7: Version Tracking")
print("="*60)

y_version_sample = get_logs_sql(
    "level: ERROR | SELECT __tag__:_image_name_ LIMIT 5",
    Y_FROM, Y_TO, "5"
)
d_version_sample = get_logs_sql(
    "level: ERROR | SELECT __tag__:_image_name_ LIMIT 5",
    D_FROM, D_TO, "5"
)

y_version = "unknown"
d_version = "unknown"

if isinstance(y_version_sample, list) and len(y_version_sample) > 0:
    img = y_version_sample[0].get("__tag__:_image_name_", "")
    if img:
        y_version = img.split(":")[-1] if ":" in img else img
    print(f"Yesterday version sample: {y_version}")
else:
    print(f"Yesterday version: unknown (result: {y_version_sample})")

if isinstance(d_version_sample, list) and len(d_version_sample) > 0:
    img = d_version_sample[0].get("__tag__:_image_name_", "")
    if img:
        d_version = img.split(":")[-1] if ":" in img else img
    print(f"Day Before version sample: {d_version}")
else:
    print(f"Day Before version: unknown (result: {d_version_sample})")

# ═══════════════════════════════════════════════════════════
# STEP 8: Time period aggregation
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 8: Time Period Aggregation")
print("="*60)

def aggregate_periods(hourly):
    periods = {
        "凌晨(00-07)": sum(v for k, v in hourly.items() if 0 <= int(k.split(":")[0]) <= 7),
        "上午(08-12)": sum(v for k, v in hourly.items() if 8 <= int(k.split(":")[0]) <= 12),
        "下午(13-17)": sum(v for k, v in hourly.items() if 13 <= int(k.split(":")[0]) <= 17),
        "晚高峰(18-20)": sum(v for k, v in hourly.items() if 18 <= int(k.split(":")[0]) <= 20),
        "夜间(21-23)": sum(v for k, v in hourly.items() if 21 <= int(k.split(":")[0]) <= 23),
    }
    return periods

y_periods = aggregate_periods(y_hourly)
d_periods = aggregate_periods(d_hourly)

for period in y_periods:
    y_val = y_periods[period]
    d_val = d_periods.get(period, 0)
    change = ""
    if d_val > 0:
        pct = (y_val - d_val) / d_val * 100
        change = f" ({pct:+.1f}%)"
    elif y_val > 0:
        change = " (NEW)"
    print(f"  {period}: Y={y_val}, D={d_val}{change}")

# ═══════════════════════════════════════════════════════════
# Save all data for report generation
# ═══════════════════════════════════════════════════════════
output = {
    "yesterday_date": "2026-08-08",
    "day_before_date": "2026-08-07",
    "y_total": y_total,
    "d_total": d_total,
    "y_hourly": y_hourly,
    "d_hourly": d_hourly,
    "y_loggers": y_loggers,
    "d_loggers": d_loggers,
    "y_msgs": y_msgs[:10],
    "d_msgs": d_msgs[:10],
    "y_keywords": y_keywords,
    "d_keywords": d_keywords,
    "y_drilldowns": y_drilldowns,
    "y_periods": y_periods,
    "d_periods": d_periods,
    "y_version": y_version,
    "d_version": d_version,
    "y_hist": y_hist if isinstance(y_hist, list) else [],
}

out_path = "/root/.hermes/workspace/sls_daily_2026-08-08.json"
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)
print(f"\nAll data saved to: {out_path}")
print("\n=== DATA COLLECTION COMPLETE ===")
