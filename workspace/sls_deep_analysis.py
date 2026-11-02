#!/usr/bin/env python3
"""SLS Error deep analysis — hourly, keyword classification, peak drill-down."""
import sys, os, json, time, re
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Timestamps
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

def get_histogram(query, from_ts, to_ts):
    return call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
    })

def get_logs(query, from_ts, to_ts, line="10"):
    return call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
        "line": line, "region": REGION,
    })

# Load existing data
with open("/root/.hermes/workspace/sls_error_daily.json") as f:
    data = json.load(f)

hist_y = data["hist_yesterday"]
hist_db = data["hist_day_before"]

# ── 1. Aggregate to hourly (CST) ──
def agg_hourly(buckets):
    hourly = {}
    for b in buckets:
        ts = b["from"]
        cst_hour = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8))).strftime("%H:00")
        hourly[cst_hour] = hourly.get(cst_hour, 0) + b["count"]
    return hourly

y_hourly = agg_hourly(hist_y)
db_hourly = agg_hourly(hist_db)

# Fill missing hours
for h in range(24):
    key = f"{h:02d}:00"
    y_hourly.setdefault(key, 0)
    db_hourly.setdefault(key, 0)

print("\n=== Yesterday Hourly (CST) ===")
for h in sorted(y_hourly.keys()):
    print(f"  {h}: {y_hourly[h]}")

print("\n=== Day-before Hourly (CST) ===")
for h in sorted(db_hourly.keys()):
    print(f"  {h}: {db_hourly[h]}")

# ── 2. Keyword classification via GetHistograms ──
keywords = [
    ("Dify中间件", "level: ERROR and \"Dify\""),
    ("DataCard中间件", "level: ERROR and \"DataCard\""),
    ("角色不存在", "level: ERROR and \"角色不存在\""),
    ("生成失败", "level: ERROR and \"生成失败\""),
    ("创建角色记录失败", "level: ERROR and \"创建角色记录失败\""),
    ("Internal Server Error", "level: ERROR and \"Internal Server Error\""),
    ("Unhandled ISE", "level: ERROR and \"Unhandled Internal Server Error\""),
    ("ASGI异常", "level: ERROR and \"Exception in ASGI\""),
    ("LingSmartClient", "level: ERROR and \"LingSmartClient\""),
    ("WALLPAPER_ERROR", "level: ERROR and \"WALLPAPER_ERROR\""),
    ("获取用户能量", "level: ERROR and \"获取用户能量\""),
    ("图片未通过风控", "level: ERROR and \"图片未通过风控\""),
    ("已经点赞", "level: ERROR and \"已经点赞\""),
    ("创作记录不存在", "level: ERROR and \"创作记录不存在\""),
    ("TTS转换异常", "level: ERROR and \"TTS转换异常\""),
    ("辩论", "level: ERROR and \"辩论\""),
    ("CDN", "level: ERROR and \"CDN\""),
    ("下载图片失败", "level: ERROR and \"下载图片失败\""),
    ("volcengineapi", "level: ERROR and \"volcengineapi\""),
    ("audio_generator", "level: ERROR and \"audio_generator\""),
    ("MQTT", "level: ERROR and \"MQTT\""),
    ("amap_client", "level: ERROR and \"amap_client\""),
    ("weapp-api请求处理异常", "level: ERROR and \"请求处理异常\""),
    ("孩子不属于你", "level: ERROR and \"孩子不属于你\""),
    ("Coze", "level: ERROR and \"Coze\""),
    ("volcengine_search", "level: ERROR and \"volcengine_search\""),
    ("lock", "level: ERROR and \"app.utils.lock\""),
    ("parental_control", "level: ERROR and \"parental_control\""),
    ("weather", "level: ERROR and \"天气API\""),
    ("Duplicate Entry", "level: ERROR and \"Duplicate entry\""),
]

print("\n=== Keyword Classification ===")
print(f"{'Category':<30} {'Yesterday':>10} {'Day-before':>10} {'Change':>10}")
print("-" * 65)

kw_results = {}
for name, query in keywords:
    y_hist = get_histogram(query, yesterday_from, yesterday_to)
    db_hist = get_histogram(query, day_before_from, day_before_to)
    y_count = sum(b.get("count", 0) for b in y_hist) if isinstance(y_hist, list) else 0
    db_count = sum(b.get("count", 0) for b in db_hist) if isinstance(db_hist, list) else 0
    change = y_count - db_count
    pct = f"{change:+d}"
    if db_count > 0:
        pct += f" ({change/db_count*100:+.0f}%)"
    print(f"{name:<30} {y_count:>10} {db_count:>10} {pct:>10}")
    kw_results[name] = {"yesterday": y_count, "day_before": db_count}

# ── 3. Peak hour drill-down ──
# Find top 3 peak hours yesterday
sorted_hours = sorted(y_hourly.items(), key=lambda x: x[1], reverse=True)
top3 = sorted_hours[:3]
print(f"\n=== Top 3 Peak Hours (Yesterday) ===")
for h, cnt in top3:
    print(f"  {h}: {cnt}")

# ── 4. Get sample logs from peak hour ──
cst_hour = top3[0][0]
hour_num = int(cst_hour.split(":")[0])
# CST → UTC
utc_hour = (hour_num - 8) % 24
base_utc = 1784304000  # yesterday 00:00:00 CST = 2026-07-17 16:00:00 UTC
peak_from = str(base_utc + utc_hour * 3600)
peak_to = str(base_utc + (utc_hour + 1) * 3600 - 1)

print(f"\n=== Peak Hour Samples (CST {cst_hour}, UTC from={peak_from} to={peak_to}) ===")
peak_logs = get_logs("level: ERROR", peak_from, peak_to, line="20")
if isinstance(peak_logs, list) and len(peak_logs) > 0:
    for i, log in enumerate(peak_logs[:10]):
        logger = log.get("logger", "N/A")
        message = log.get("message", "N/A")[:150]
        print(f"  [{i+1}] logger={logger}")
        print(f"      msg={message}")
        print()
else:
    print("  No samples returned (trying fallback with broader query)")
    # Fallback: get samples from a nearby bucket that has data
    peak_logs = get_logs("level: ERROR", yesterday_from, yesterday_to, line="10")
    if isinstance(peak_logs, list) and len(peak_logs) > 0:
        for i, log in enumerate(peak_logs[:10]):
            logger = log.get("logger", "N/A")
            message = log.get("message", "N/A")[:150]
            print(f"  [{i+1}] logger={logger}")
            print(f"      msg={message}")
            print()
    else:
        print("  No samples available")

# ── 5. Version check ──
print("\n=== Version Check ===")
ver_logs = get_logs("level: ERROR", yesterday_from, str(int(yesterday_from) + 60), line="5")
if isinstance(ver_logs, list) and len(ver_logs) > 0:
    for log in ver_logs[:3]:
        img = log.get("__tag__:_image_name_", "unknown")
        print(f"  Image: {img}")
else:
    # Try end of day
    ver_logs = get_logs("level: ERROR", str(int(yesterday_to) - 60), yesterday_to, line="5")
    if isinstance(ver_logs, list) and len(ver_logs) > 0:
        for log in ver_logs[:3]:
            img = log.get("__tag__:_image_name_", "unknown")
            print(f"  Image: {img}")
    else:
        print("  No version info available from ERROR logs")

# ── 6. Time period aggregation ──
def period_agg(hourly, ranges):
    result = {}
    for name, start, end in ranges:
        total = 0
        for h in range(start, end + 1):
            key = f"{h:02d}:00"
            total += hourly.get(key, 0)
        result[name] = total
    return result

ranges = [
    ("凌晨(00-07)", 0, 7),
    ("上午(08-12)", 8, 12),
    ("下午(13-17)", 13, 17),
    ("晚高峰(18-20)", 18, 20),
    ("夜间(21-23)", 21, 23),
]

print("\n=== Period Aggregation ===")
y_periods = period_agg(y_hourly, ranges)
db_periods = period_agg(db_hourly, ranges)
print(f"{'Period':<20} {'Yesterday':>10} {'Day-before':>10} {'Change':>12}")
print("-" * 55)
for name, _, _ in ranges:
    y_val = y_periods[name]
    db_val = db_periods[name]
    ch = y_val - db_val
    pct = f"{ch:+d}"
    if db_val > 0:
        pct += f" ({ch/db_val*100:+.0f}%)"
    print(f"{name:<20} {y_val:>10} {db_val:>10} {pct:>12}")

# ── 7. Day-before peak hour drill-down ──
db_sorted = sorted(db_hourly.items(), key=lambda x: x[1], reverse=True)
db_top3 = db_sorted[:3]
print(f"\n=== Day-before Top 3 Peak Hours ===")
for h, cnt in db_top3:
    print(f"  {h}: {cnt}")

print("\nDONE")
