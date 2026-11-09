#!/usr/bin/env python3
"""Daily SLS Error Analysis — queries leap-online/ling-server for yesterday and day-before.
Usage: python3 scripts/daily_error_query.py
Output: /root/.hermes/workspace/sls_daily_YYYY-MM-DD.json

Requires: hermes-rds-daemon (auto-restarts). No rds_security toolset needed.
"""
import sys, os, json, time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

cst = timezone(timedelta(hours=8))
now = datetime.now(cst)
yesterday_start = datetime(now.year, now.month, now.day, tzinfo=cst) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

YESTERDAY_FROM = str(int(yesterday_start.timestamp()))
YESTERDAY_TO = str(int(yesterday_end.timestamp()))
DAY_BEFORE_FROM = str(int(day_before_start.timestamp()))
DAY_BEFORE_TO = str(int(day_before_end.timestamp()))
DATE_STR = yesterday_start.strftime("%Y-%m-%d")

client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(2)
client.ensure_daemon_running()
time.sleep(2)
client.send_request({"action": "register_caller"}, timeout_s=5)

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

results = {}

# 1. GetHistograms (yesterday + day before)
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    h = call_sls("GetHistograms", {"project": PROJECT, "logstore": LOGSTORE, "query": "level: ERROR", "from": fr, "to": to})
    total = sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0
    results[f"hist_{label}"] = {"buckets": h, "total": total}

# 2. Hourly distribution via SQL
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    h = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
        "from": fr, "to": to, "line": "50",
    })
    results[f"hourly_{label}"] = h

# 3. Top loggers
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    l = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
        "from": fr, "to": to, "line": "50",
    })
    results[f"loggers_{label}"] = l

# 4. Top messages
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    m = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
        "from": fr, "to": to, "line": "50",
    })
    results[f"messages_{label}"] = m

# 5. Keyword: netease 3100 (Chinese-text errors not caught by plain GetHistograms)
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    h = call_sls("GetHistograms", {"project": PROJECT, "logstore": LOGSTORE, "query": "level: ERROR and 3100", "from": fr, "to": to})
    results[f"netease_3100_{label}"] = sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0

# 6. Keyword: NoneType
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    h = call_sls("GetHistograms", {"project": PROJECT, "logstore": LOGSTORE, "query": "level: ERROR and NoneType", "from": fr, "to": to})
    results[f"nonetype_{label}"] = sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0

# 7. VOIP keywords
for kw in ["TaskConflict", "voip call has been exist", "GetLicense"]:
    for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
        h = call_sls("GetHistograms", {"project": PROJECT, "logstore": LOGSTORE, "query": f"level: ERROR and {kw}", "from": fr, "to": to})
        results[f'voip_{kw.replace(" ", "_")}_{label}'] = sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0

# 8. ai_camera JSON errors
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    m = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR and ai_camera and JSONDecodeError | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
        "from": fr, "to": to, "line": "20",
    })
    total = sum(int(r.get("cnt", 0)) for r in m) if isinstance(m, list) else 0
    results[f'ai_camera_json_{label}'] = {"total": total, "rows": m}

# 9. weapp_device_status
for label, fr, to in [("yesterday", YESTERDAY_FROM, YESTERDAY_TO), ("day_before", DAY_BEFORE_FROM, DAY_BEFORE_TO)]:
    m = call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": "level: ERROR | SELECT count(1) as cnt, logger, substr(message, 1, 200) as msg_sample WHERE logger = 'app.controllers.weapp_device_status' GROUP BY logger, msg_sample ORDER BY cnt DESC LIMIT 10",
        "from": fr, "to": to, "line": "20",
    })
    total = sum(int(r.get("cnt", 0)) for r in m) if isinstance(m, list) else 0
    results[f'weapp_device_status_{label}'] = {"total": total, "rows": m}

out_path = f"/root/.hermes/workspace/sls_daily_{DATE_STR}.json"
with open(out_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"Results saved to {out_path}")
print(f"Yesterday total: {results['hist_yesterday']['total']}, Day before total: {results['hist_day_before']['total']}")
