#!/usr/bin/env python3
"""SLS daily error analysis for 2026-08-13 vs 2026-08-12"""
import sys, os, json, time

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

# Timestamps (CST dates → UTC timestamps)
YESTERDAY_FROM = "1786550400"   # 2026-08-13 00:00:00 CST
YESTERDAY_TO   = "1786636799"   # 2026-08-13 23:59:59 CST
DAYBEFORE_FROM = "1786464000"   # 2026-08-12 00:00:00 CST
DAYBEFORE_TO   = "1786550399"   # 2026-08-12 23:59:59 CST

client = DaemonClient()

# Step 1: Kill existing daemon
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)

# Step 2: Start fresh daemon
client.ensure_daemon_running()
time.sleep(1)

# Step 3: Register
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Register: {json.dumps(resp)}")

# Step 4: Query helper
def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

# ===== 1. Histograms for both days =====
hist_yesterday = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
})

hist_daybefore = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
})

yesterday_total = sum(b["count"] for b in hist_yesterday) if isinstance(hist_yesterday, list) else 0
daybefore_total = sum(b["count"] for b in hist_daybefore) if isinstance(hist_daybefore, list) else 0

print(f"\n=== Histogram totals ===")
print(f"Yesterday (08-13): {yesterday_total} errors")
print(f"Day before (08-12): {daybefore_total} errors")

# ===== 2. Hourly distribution via SQL =====
def get_hourly(from_ts, to_ts, label):
    result = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
        "from": from_ts, "to": to_ts, "line": "50",
    })
    if isinstance(result, list):
        hourly = {}
        for row in result:
            hourly[row.get("hour", "")] = int(row.get("cnt", 0))
        print(f"\n=== {label} Hourly Distribution ===")
        for h in sorted(hourly.keys()):
            print(f"  {h}: {hourly[h]}")
        return hourly
    else:
        print(f"\n=== {label} Hourly Distribution: {result}")
        return {}

hourly_yesterday = get_hourly(YESTERDAY_FROM, YESTERDAY_TO, "Yesterday 08-13")
hourly_daybefore = get_hourly(DAYBEFORE_FROM, DAYBEFORE_TO, "Day Before 08-12")

# ===== 3. Top Loggers =====
def get_top_loggers(from_ts, to_ts, label):
    result = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 15",
        "from": from_ts, "to": to_ts, "line": "50",
    })
    if isinstance(result, list):
        print(f"\n=== {label} Top Loggers ===")
        loggers = []
        for row in result:
            loggers.append((row.get("logger", "unknown"), int(row.get("cnt", 0))))
            print(f"  {loggers[-1][0]}: {loggers[-1][1]}")
        return loggers
    else:
        print(f"\n=== {label} Top Loggers: {result}")
        return []

loggers_yesterday = get_top_loggers(YESTERDAY_FROM, YESTERDAY_TO, "Yesterday 08-13")
loggers_daybefore = get_top_loggers(DAYBEFORE_FROM, DAYBEFORE_TO, "Day Before 08-12")

# ===== 4. Top Error Messages =====
def get_top_messages(from_ts, to_ts, label):
    result = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
        "from": from_ts, "to": to_ts, "line": "50",
    })
    if isinstance(result, list):
        print(f"\n=== {label} Top Error Messages ===")
        messages = []
        for row in result:
            messages.append((row.get("msg_sample", "")[:100], int(row.get("cnt", 0))))
            print(f"  [{messages[-1][1]}] {messages[-1][0]}")
        return messages
    else:
        print(f"\n=== {label} Top Error Messages: {result}")
        return []

messages_yesterday = get_top_messages(YESTERDAY_FROM, YESTERDAY_TO, "Yesterday 08-13")
messages_daybefore = get_top_messages(DAYBEFORE_FROM, DAYBEFORE_TO, "Day Before 08-12")

# ===== 5. Keyword-based error classification (GetHistograms) =====
print(f"\n=== Error Classification (GetHistograms) ===")
keywords = ["Dify", "DataCard", "LingSmartClient", "Unhandled Internal Server Error", 
            "Exception in ASGI", "角色不存在", "生成失败", "图片未通过风控",
            "任务状态不正确", "已经点赞", "Magic"]

for kw in keywords:
    hy = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f'level: ERROR and "{kw}"',
        "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    })
    hb = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f'level: ERROR and "{kw}"',
        "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
    })
    cy = sum(b["count"] for b in hy) if isinstance(hy, list) else 0
    cb = sum(b["count"] for b in hb) if isinstance(hb, list) else 0
    print(f"  {kw}: yesterday={cy}, daybefore={cb}")

# ===== 6. Peak hour drill-down (top 3 hours yesterday) =====
print(f"\n=== Peak Hour Drill-down (Yesterday) ===")
sorted_hours = sorted(hourly_yesterday.items(), key=lambda x: x[1], reverse=True)
for hour, count in sorted_hours[:3]:
    cst_h = int(hour.split(":")[0])
    utc_h = (cst_h - 8) % 24
    base_utc = 1786550400
    window_from = base_utc + utc_h * 3600
    window_to = window_from + 3600
    
    drill = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"level: ERROR and __time__ >= {window_from} and __time__ < {window_to} | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 10",
        "from": str(window_from), "to": str(window_to), "line": "30",
    })
    print(f"\n  Hour {hour} CST ({count} errors):")
    if isinstance(drill, list):
        for row in drill:
            print(f"    {row.get('logger', 'unknown')}: {row.get('cnt', 0)}")
    else:
        print(f"    {drill}")

# ===== 7. Save JSON output =====
output = {
    "date": "2026-08-13",
    "compare_date": "2026-08-12",
    "yesterday_total": yesterday_total,
    "daybefore_total": daybefore_total,
    "hourly_yesterday": hourly_yesterday,
    "hourly_daybefore": hourly_daybefore,
    "loggers_yesterday": loggers_yesterday,
    "loggers_daybefore": loggers_daybefore,
    "messages_yesterday": messages_yesterday,
    "messages_daybefore": messages_daybefore,
    "hist_yesterday": hist_yesterday if isinstance(hist_yesterday, list) else [],
    "hist_daybefore": hist_daybefore if isinstance(hist_daybefore, list) else [],
}

with open("/root/.hermes/workspace/sls_daily_2026-08-13.json", "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n=== Output saved to /root/.hermes/workspace/sls_daily_2026-08-13.json ===")
