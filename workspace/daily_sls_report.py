#!/usr/bin/env python3
"""Daily SLS Error Analysis — ling-server, yesterday vs day before.
Outputs JSON to /root/.hermes/workspace/sls_daily_YYYY-MM-DD.json
"""
import sys, os, json, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"
QUERY = "level: ERROR"

# ── Time calculation (CST-aware) ──────────────────────────────────────
cst = timezone(timedelta(hours=8))
now = datetime.now(cst)
yesterday_start = datetime(now.year, now.month, now.day, tzinfo=cst) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

y_from = str(int(yesterday_start.timestamp()))
y_to = str(int(yesterday_end.timestamp()))
d_from = str(int(day_before_start.timestamp()))
d_to = str(int(day_before_end.timestamp()))

yesterday_str = yesterday_start.strftime("%Y-%m-%d")
day_before_str = day_before_start.strftime("%Y-%m-%d")

print(f"Yesterday: {yesterday_str} ({y_from} → {y_to})")
print(f"Day Before: {day_before_str} ({d_from} → {d_to})")

# ── Daemon restart ──────────────────────────────────────────────────────
client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)
client.ensure_daemon_running()
time.sleep(1)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
assert resp.get("status") == "success", f"Failed: {resp}"
print("Daemon registered OK")

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

def histogram_total(query, from_ts, to_ts):
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
    })
    return sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0

def sql_agg(query, from_ts, to_ts, line="50"):
    return call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"{QUERY} | {query}",
        "from": from_ts, "to": to_ts, "line": line, "region": REGION,
    })

# ── Queries ─────────────────────────────────────────────────────────────
# 1. Totals
total_y = histogram_total(QUERY, y_from, y_to)
total_d = histogram_total(QUERY, d_from, d_to)
print(f"Totals: Y={total_y}, D={total_d}")

# 2. Hourly distribution
hourly_y = sql_agg(
    "SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    y_from, y_to)
hourly_d = sql_agg(
    "SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    d_from, d_to)

hour_dict_y = {h.get("hour"): int(h.get("cnt", 0)) for h in (hourly_y if isinstance(hourly_y, list) else [])}
hour_dict_d = {h.get("hour"): int(h.get("cnt", 0)) for h in (hourly_d if isinstance(hourly_d, list) else [])}
for hh in range(24):
    hour_dict_y.setdefault("%02d:00" % hh, 0)
    hour_dict_d.setdefault("%02d:00" % hh, 0)

# 3. Top loggers
loggers_y = sql_agg("SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20", y_from, y_to)
loggers_d = sql_agg("SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20", d_from, d_to)

logger_dict_y = {l.get("logger"): int(l.get("cnt", 0)) for l in (loggers_y if isinstance(loggers_y, list) else [])}
logger_dict_d = {l.get("logger"): int(l.get("cnt", 0)) for l in (loggers_d if isinstance(loggers_d, list) else [])}

# 4. Top error messages
msgs_y = sql_agg("SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15", y_from, y_to)
msgs_d = sql_agg("SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15", d_from, d_to)

msg_list_y = [{"cnt": int(m.get("cnt", 0)), "msg": m.get("msg_sample", "")[:200]} for m in (msgs_y if isinstance(msgs_y, list) else [])]
msg_list_d = [{"cnt": int(m.get("cnt", 0)), "msg": m.get("msg_sample", "")[:200]} for m in (msgs_d if isinstance(msgs_d, list) else [])]

# 5. Version tracking
ver_sample = lambda from_ts, to_ts: call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE, "query": QUERY,
    "from": from_ts, "to": str(int(from_ts) + 60), "line": "3", "region": REGION,
})
def extract_version(sample):
    if isinstance(sample, list) and len(sample) > 0:
        img = sample[0].get("__tag__:_image_name_", "")
        return img.split(":")[-1] if ":" in img else img
    return "unknown"
version_y = extract_version(ver_sample(y_from, y_to))
version_d = extract_version(ver_sample(d_from, d_to))

# 6. Peak hour drill-down
def cst_hour_to_utc_ts(base_utc_ts, cst_hour_str):
    cst_h = int(cst_hour_str.split(":")[0])
    utc_h = (cst_h - 8) % 24
    return base_utc_ts + utc_h * 3600

peak_y_hour = max(hour_dict_y, key=hour_dict_y.get) if hour_dict_y else "00:00"
peak_d_hour = max(hour_dict_d, key=hour_dict_d.get) if hour_dict_d else "00:00"

y_base_utc = int(yesterday_start.timestamp())
d_base_utc = int(day_before_start.timestamp())

peak_y_start = cst_hour_to_utc_ts(y_base_utc, peak_y_hour)
peak_y_end = peak_y_start + 3600
drill_y = sql_agg("SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10", str(peak_y_start), str(peak_y_end), "30")

peak_d_start = cst_hour_to_utc_ts(d_base_utc, peak_d_hour)
peak_d_end = peak_d_start + 3600
drill_d = sql_agg("SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10", str(peak_d_start), str(peak_d_end), "30")

# 7. Keyword classification (GetHistograms)
keywords = [
    ("Dify", "Dify相关错误"), ("DataCard", "DataCard相关错误"),
    ("生成失败", "生成失败"), ("创建角色记录失败", "创建角色记录失败"),
    ("任务状态不正确", "任务状态不正确"),
    ("Internal Server Error", "Internal Server Error"),
    ("Exception in ASGI", "ASGI异常"),
    ("角色不存在", "角色不存在"), ("孩子不属于你", "孩子不属于你"),
    ("LingSmartClient", "LingSmartClient连接"),
    ("图片未通过风控", "图片未通过风控"),
    ("Dify工作流执行失败", "Dify工作流执行失败"),
    ("已经点赞", "已经点赞"),
    ("创作记录不存在", "创作记录不存在"),
    ("SQLAlchemy", "SQLAlchemy错误"), ("pymysql", "pymysql错误"),
    ("OperationalError", "OperationalError"), ("IntegrityError", "IntegrityError"),
    ("ConnectionError", "ConnectionError"), ("timeout", "timeout错误"),
    ("TimeoutError", "TimeoutError"),
    ("KeyError", "KeyError"), ("IndexError", "IndexError代码Bug"),
    ("TypeError", "TypeError"),
]
kw_results_y, kw_results_d = {}, {}
for kw, label in keywords:
    cnt_y = histogram_total(f'{QUERY} and "{kw}"', y_from, y_to)
    cnt_d = histogram_total(f'{QUERY} and "{kw}"', d_from, d_to)
    if cnt_y > 0 or cnt_d > 0:
        kw_results_y[label] = cnt_y
        kw_results_d[label] = cnt_d

# 8. Root logger
root_msgs_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f'{QUERY} and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10',
    "from": y_from, "to": y_to, "line": "30", "region": REGION,
})
root_msgs_d = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": f'{QUERY} and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10',
    "from": d_from, "to": d_to, "line": "30", "region": REGION,
})

# ── Save ─────────────────────────────────────────────────────────────────
output = {
    "yesterday_date": yesterday_str, "day_before_date": day_before_str,
    "total_y": total_y, "total_d": total_d,
    "version_y": version_y, "version_d": version_d,
    "hour_dict_y": hour_dict_y, "hour_dict_d": hour_dict_d,
    "logger_dict_y": logger_dict_y, "logger_dict_d": logger_dict_d,
    "msg_list_y": msg_list_y, "msg_list_d": msg_list_d,
    "kw_results_y": kw_results_y, "kw_results_d": kw_results_d,
    "root_total_y": logger_dict_y.get("root", 0),
    "root_total_d": logger_dict_d.get("root", 0),
    "peak_y_hour": peak_y_hour, "peak_d_hour": peak_d_hour,
    "drill_y": drill_y if isinstance(drill_y, list) else [],
    "drill_d": drill_d if isinstance(drill_d, list) else [],
    "root_msgs_y": root_msgs_y if isinstance(root_msgs_y, list) else [],
    "root_msgs_d": root_msgs_d if isinstance(root_msgs_d, list) else [],
}

out_path = f"/root/.hermes/workspace/sls_daily_{yesterday_str}.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)
print(f"\nData saved to: {out_path}")
