#!/usr/bin/env python3
"""SLS daily error query via daemon restart — full dual-day comparison."""
import sys, os, json, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

# ── Constants ──
AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# ── Timestamps ──
cst = timezone(timedelta(hours=8))
now_cst = datetime.now(cst)
yesterday_start = datetime(now_cst.year, now_cst.month, now_cst.day, tzinfo=cst) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

Y_FROM = int(yesterday_start.timestamp())
Y_TO = int(yesterday_end.timestamp())
D_FROM = int(day_before_start.timestamp())
D_TO = int(day_before_end.timestamp())

yesterday_date = yesterday_start.strftime("%Y-%m-%d")
daybefore_date = day_before_start.strftime("%Y-%m-%d")

print(f"昨天 ({yesterday_date}): from={Y_FROM}, to={Y_TO}")
print(f"前天 ({daybefore_date}): from={D_FROM}, to={D_TO}")

# ── Daemon setup ──
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(2)

client = DaemonClient()
client.ensure_daemon_running()
time.sleep(2)

resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Daemon register: {json.dumps(resp)}")

# ── API helper ──
def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def get_histograms(query, from_ts, to_ts):
    return call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": str(from_ts), "to": str(to_ts),
    })

def get_logs(query, from_ts, to_ts, line="50"):
    return call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": str(from_ts), "to": str(to_ts),
        "line": line, "region": REGION,
    })

def histogram_total(hist):
    if isinstance(hist, list):
        return sum(b.get("count", 0) for b in hist)
    return 0

def hourly_from_histogram(hist):
    """Aggregate 30-min histogram buckets into hourly counts."""
    hourly = {}
    if not isinstance(hist, list):
        return hourly
    for b in hist:
        ts = b.get("from", 0)
        cst_hour = datetime.fromtimestamp(ts, tz=cst).strftime("%H:00")
        hourly[cst_hour] = hourly.get(cst_hour, 0) + b.get("count", 0)
    return hourly

# ═══════════════════════════════════════
# 1. Total error counts via GetHistograms
# ═══════════════════════════════════════
print("\n[1] Fetching total error counts via GetHistograms...")
y_hist = get_histograms("level: ERROR", Y_FROM, Y_TO)
d_hist = get_histograms("level: ERROR", D_FROM, D_TO)
y_total = histogram_total(y_hist)
d_total = histogram_total(d_hist)
print(f"  昨天 total: {y_total}")
print(f"  前天 total: {d_total}")

# ═══════════════════════════════════════
# 2. Hourly distribution via SQL
# ═══════════════════════════════════════
print("\n[2] Fetching hourly distribution via SQL...")
hourly_sql = "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour"
y_hourly_raw = get_logs(hourly_sql, Y_FROM, Y_TO, line="50")
d_hourly_raw = get_logs(hourly_sql, D_FROM, D_TO, line="50")

y_hourly = {}
d_hourly = {}

if isinstance(y_hourly_raw, list) and len(y_hourly_raw) > 0:
    for r in y_hourly_raw:
        h = r.get("hour", "")
        c = int(r.get("cnt", 0))
        if h:
            y_hourly[h] = c
    print(f"  昨天 SQL hourly: {len(y_hourly)} hours")
else:
    y_hourly = hourly_from_histogram(y_hist)
    print(f"  昨天 SQL empty, fallback to histogram: {len(y_hourly)} hours")

if isinstance(d_hourly_raw, list) and len(d_hourly_raw) > 0:
    for r in d_hourly_raw:
        h = r.get("hour", "")
        c = int(r.get("cnt", 0))
        if h:
            d_hourly[h] = c
    print(f"  前天 SQL hourly: {len(d_hourly)} hours")
else:
    d_hourly = hourly_from_histogram(d_hist)
    print(f"  前天 SQL empty, fallback to histogram: {len(d_hourly)} hours")

# Fill missing hours
for h in range(24):
    hk = f"{h:02d}:00"
    y_hourly.setdefault(hk, 0)
    d_hourly.setdefault(hk, 0)

# ═══════════════════════════════════════
# 3. Top loggers via SQL
# ═══════════════════════════════════════
print("\n[3] Fetching top loggers via SQL...")
logger_sql = "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20"
y_logger_raw = get_logs(logger_sql, Y_FROM, Y_TO, line="50")
d_logger_raw = get_logs(logger_sql, D_FROM, D_TO, line="50")

y_loggers = {}
d_loggers = {}

if isinstance(y_logger_raw, list):
    for r in y_logger_raw:
        lg = r.get("logger", "unknown")
        c = int(r.get("cnt", 0))
        if lg:
            y_loggers[lg] = c
    print(f"  昨天 loggers: {len(y_loggers)}")

if isinstance(d_logger_raw, list):
    for r in d_logger_raw:
        lg = r.get("logger", "unknown")
        c = int(r.get("cnt", 0))
        if lg:
            d_loggers[lg] = c
    print(f"  前天 loggers: {len(d_loggers)}")

# ═══════════════════════════════════════
# 4. Top error messages via SQL
# ═══════════════════════════════════════
print("\n[4] Fetching top error messages via SQL...")
msg_sql = "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20"
y_msg_raw = get_logs(msg_sql, Y_FROM, Y_TO, line="50")
d_msg_raw = get_logs(msg_sql, D_FROM, D_TO, line="50")

y_messages = []
d_messages = []

if isinstance(y_msg_raw, list):
    for r in y_msg_raw:
        c = int(r.get("cnt", 0))
        m = r.get("msg_sample", "")[:150]
        y_messages.append((c, m))
    print(f"  昨天 messages: {len(y_messages)}")

if isinstance(d_msg_raw, list):
    for r in d_msg_raw:
        c = int(r.get("cnt", 0))
        m = r.get("msg_sample", "")[:150]
        d_messages.append((c, m))
    print(f"  前天 messages: {len(d_messages)}")

# ═══════════════════════════════════════
# 5. Category counts via GetHistograms
# ═══════════════════════════════════════
print("\n[5] Fetching category counts via GetHistograms...")
categories = {
    "Dify中间件": "level: ERROR and \"Dify\"",
    "DataCard中间件": "level: ERROR and \"DataCard\"",
    "角色不存在": "level: ERROR and \"角色不存在\"",
    "任务生成失败": "level: ERROR and \"生成失败\"",
    "图片未通过风控": "level: ERROR and \"图片未通过风控\"",
    "LingSmartClient": "level: ERROR and \"LingSmartClient\"",
    "WALLPAPER_ERROR": "level: ERROR and \"WALLPAPER_ERROR\"",
    "Internal Server Error": "level: ERROR and \"Internal Server Error\"",
    "Exception in ASGI": "level: ERROR and \"Exception in ASGI\"",
    "已经点赞": "level: ERROR and \"已经点赞\"",
    "孩子不属于你": "level: ERROR and \"孩子不属于你\"",
    "Duplicate Entry": "level: ERROR and \"Duplicate Entry\"",
}

y_categories = {}
d_categories = {}
for name, query in categories.items():
    yh = histogram_total(get_histograms(query, Y_FROM, Y_TO))
    dh = histogram_total(get_histograms(query, D_FROM, D_TO))
    y_categories[name] = yh
    d_categories[name] = dh
    print(f"  {name}: 昨天={yh}, 前天={dh}")

# ═══════════════════════════════════════
# 6. Version tracking
# ═══════════════════════════════════════
print("\n[6] Fetching version info...")
ver_sql = "level: ERROR | SELECT __tag__:__image_name__ as image, count(1) as cnt GROUP BY image ORDER BY cnt DESC LIMIT 5"
y_ver_raw = get_logs(ver_sql, Y_FROM, Y_TO, line="10")
if isinstance(y_ver_raw, list) and len(y_ver_raw) > 0:
    y_version = y_ver_raw[0].get("image", "unknown") if y_ver_raw[0].get("image") else "unknown"
    print(f"  昨天版本: {y_version}")
else:
    y_version = "unknown"
    print(f"  昨天版本: unknown (no error logs in query window)")

# ═══════════════════════════════════════
# 7. Peak hour drill-down
# ═══════════════════════════════════════
print("\n[7] Peak hour analysis...")
y_sorted_hours = sorted(y_hourly.items(), key=lambda x: x[1], reverse=True)
top3_hours = y_sorted_hours[:3]
print(f"  昨天 Top 3 hours: {top3_hours}")

peak_logger_data = {}
for hour_str, count in top3_hours:
    if count == 0:
        continue
    utc_hour = (int(hour_str.split(":")[0]) - 8) % 24
    base_utc = Y_FROM - (Y_FROM % 86400)  # UTC 00:00 of yesterday
    drill_from = base_utc + utc_hour * 3600
    drill_to = drill_from + 3600
    
    drill_sql = f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10"
    drill_raw = get_logs(drill_sql, drill_from, drill_to, line="30")
    
    peak_logger_data[hour_str] = {}
    if isinstance(drill_raw, list):
        for r in drill_raw:
            lg = r.get("logger", "unknown")
            c = int(r.get("cnt", 0))
            if lg:
                peak_logger_data[hour_str][lg] = c

# ═══════════════════════════════════════
# 8. root logger analysis
# ═══════════════════════════════════════
print("\n[8] Root logger analysis...")
root_sql = "level: ERROR and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15"
y_root_raw = get_logs(root_sql, Y_FROM, Y_TO, line="30")
y_root_messages = []
if isinstance(y_root_raw, list):
    for r in y_root_raw:
        c = int(r.get("cnt", 0))
        m = r.get("msg_sample", "")[:150]
        y_root_messages.append((c, m))
    print(f"  昨天 root messages: {len(y_root_messages)}")

# ═══════════════════════════════════════
# Save results as JSON for report generation
# ═══════════════════════════════════════
output = {
    "date": yesterday_date,
    "daybefore_date": daybefore_date,
    "yesterday": {
        "total": y_total,
        "hourly": y_hourly,
        "loggers": y_loggers,
        "messages": y_messages,
        "categories": y_categories,
        "version": y_version,
        "top3_hours": top3_hours,
        "peak_drilldown": peak_logger_data,
        "root_messages": y_root_messages,
    },
    "daybefore": {
        "total": d_total,
        "hourly": d_hourly,
        "loggers": d_loggers,
        "categories": d_categories,
        "messages": d_messages,
    },
}

outpath = f"/root/.hermes/workspace/sls_daily_{yesterday_date}.json"
with open(outpath, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n✅ Results saved to {outpath}")
print(json.dumps(output, ensure_ascii=False, indent=2)[:5000])
