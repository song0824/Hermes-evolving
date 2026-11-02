#!/usr/bin/env python3
"""Complete SLS daily error analysis for 2026-08-13 vs 2026-08-12"""
import sys, os, json, time

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

YESTERDAY_FROM = "1786550400"
YESTERDAY_TO   = "1786636799"
DAYBEFORE_FROM = "1786464000"
DAYBEFORE_TO   = "1786550399"

client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)
client.ensure_daemon_running()
time.sleep(1)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Register: {json.dumps(resp)}")

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

all_data = {}

# ===== 1. Histograms =====
for label, from_ts, to_ts in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("daybefore", DAYBEFORE_FROM, DAYBEFORE_TO)]:
    hist = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR",
        "from": from_ts, "to": to_ts,
    })
    total = sum(b["count"] for b in hist) if isinstance(hist, list) else 0
    all_data[f"hist_{label}"] = hist if isinstance(hist, list) else []
    all_data[f"total_{label}"] = total
    print(f"Total {label}: {total}")

# ===== 2. Hourly distribution =====
for label, from_ts, to_ts in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("daybefore", DAYBEFORE_FROM, DAYBEFORE_TO)]:
    result = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
        "from": from_ts, "to": to_ts, "line": "50",
    })
    hourly = {}
    if isinstance(result, list):
        for row in result:
            hourly[row.get("hour", "")] = int(row.get("cnt", 0))
    all_data[f"hourly_{label}"] = hourly
    print(f"\nHourly {label}:")
    for h in sorted(hourly.keys()):
        print(f"  {h}: {hourly[h]}")

# ===== 3. Top Loggers =====
for label, from_ts, to_ts in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("daybefore", DAYBEFORE_FROM, DAYBEFORE_TO)]:
    result = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 15",
        "from": from_ts, "to": to_ts, "line": "50",
    })
    loggers = []
    if isinstance(result, list):
        for row in result:
            loggers.append((row.get("logger", "unknown"), int(row.get("cnt", 0))))
    all_data[f"loggers_{label}"] = loggers
    print(f"\nTop Loggers {label}:")
    for name, cnt in loggers:
        print(f"  {name}: {cnt}")

# ===== 4. Top Messages =====
for label, from_ts, to_ts in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("daybefore", DAYBEFORE_FROM, DAYBEFORE_TO)]:
    result = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
        "from": from_ts, "to": to_ts, "line": "50",
    })
    messages = []
    if isinstance(result, list):
        for row in result:
            messages.append((row.get("msg_sample", "")[:150], int(row.get("cnt", 0))))
    all_data[f"messages_{label}"] = messages
    print(f"\nTop Messages {label}:")
    for msg, cnt in messages:
        print(f"  [{cnt}] {msg}")

# ===== 5. Keyword classification =====
keywords = ["Dify", "DataCard", "LingSmartClient", "Unhandled Internal Server Error", 
            "Exception in ASGI", "角色不存在", "生成失败", "图片未通过风控"]
classification = {}
for label, from_ts, to_ts in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("daybefore", DAYBEFORE_FROM, DAYBEFORE_TO)]:
    classification[label] = {}
    for kw in keywords:
        hist = call_sls("GetHistograms", {
            "project": PROJECT, "logstore": LOGSTORE,
            "query": f'level: ERROR and "{kw}"',
            "from": from_ts, "to": to_ts,
        })
        cnt = sum(b["count"] for b in hist) if isinstance(hist, list) else 0
        classification[label][kw] = cnt
        print(f"  {label} '{kw}': {cnt}")

all_data["classification"] = classification

# ===== 6. Drill-down for peak hours =====
print("\n=== Peak Hour Drill-downs ===")

# Yesterday peak: 00:00 (39), 05:00 (32), 20:00 (32)
for label, base_ts, hours in [("yesterday", 1786550400, [0, 5, 20]), ("daybefore", 1786464000, [0, 1, 20])]:
    for cst_h in hours:
        window_from = base_ts + cst_h * 3600
        window_to = window_from + 3600
        
        drill = call_sls("GetLogs", {
            "project": PROJECT, "logstore": LOGSTORE,
            "query": f"level: ERROR and __time__ >= {window_from} and __time__ < {window_to} | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
            "from": str(window_from), "to": str(window_to), "line": "30",
        })
        
        if isinstance(drill, list):
            drill_loggers = [(row.get("logger", "unknown"), int(row.get("cnt", 0))) for row in drill]
        else:
            drill_loggers = []
        
        key = f"drill_{label}_{cst_h:02d}"
        all_data[key] = drill_loggers
        
        print(f"\n  {label} {cst_h:02d}:00 CST:")
        for name, cnt in drill_loggers:
            print(f"    {name}: {cnt}")

# ===== 7. Logger-specific message breakdown =====
for label, from_ts, to_ts in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("daybefore", DAYBEFORE_FROM, DAYBEFORE_TO)]:
    for logger_name in ["app.controllers.weapp_index", "app.exception_handlers", "root", "app.utils.task_scheduler"]:
        result = call_sls("GetLogs", {
            "project": PROJECT, "logstore": LOGSTORE,
            "query": f"level: ERROR and logger: {logger_name} | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
            "from": from_ts, "to": to_ts, "line": "50",
        })
        msgs = []
        if isinstance(result, list):
            for row in result:
                msgs.append((row.get("msg_sample", "")[:120], int(row.get("cnt", 0))))
        all_data[f"messages_{label}_{logger_name}"] = msgs
        
        if msgs:
            print(f"\n  {label} {logger_name} messages:")
            for msg, cnt in msgs:
                print(f"    [{cnt}] {msg}")

# ===== 8. Period aggregates =====
periods = {
    "凌晨(00-07)": (0, 8),
    "上午(08-12)": (8, 13),
    "下午(13-17)": (13, 18),
    "晚高峰(18-20)": (18, 21),
    "夜间(21-23)": (21, 24),
}

period_data = {}
for label in ["yesterday", "daybefore"]:
    hourly = all_data[f"hourly_{label}"]
    period_data[label] = {}
    for name, (start, end) in periods.items():
        total = sum(hourly.get(f"{h:02d}:00", 0) for h in range(start, end))
        period_data[label][name] = total

all_data["periods"] = period_data

print("\n=== Period Aggregates ===")
for pname in periods:
    y = period_data["yesterday"].get(pname, 0)
    d = period_data["daybefore"].get(pname, 0)
    pct = ((y - d) / d * 100) if d > 0 else 0
    print(f"  {pname}: yesterday={y}, daybefore={d}, change={pct:+.1f}%")

# ===== 9. Save =====
with open("/root/.hermes/workspace/sls_daily_2026-08-13.json", "w") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print(f"\n=== All data saved ===")
print(json.dumps(all_data, ensure_ascii=False, indent=2)[:3000])
