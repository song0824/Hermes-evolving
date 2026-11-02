#!/usr/bin/env python3
"""SLS daily error analysis for 2026-09-01 (yesterday) vs 2026-08-31 (day before)."""
import sys, os, json, time

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

YESTERDAY_FROM = "1788192000"
YESTERDAY_TO = "1788278399"
DAY_BEFORE_FROM = "1788105600"
DAY_BEFORE_TO = "1788191999"

client = DaemonClient()

# Kill existing daemon and start fresh
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

results = {}

# 1. GetHistograms for yesterday
print("Querying yesterday histogram...")
hist_y = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
})
results['hist_yesterday'] = hist_y
yesterday_total = sum(b["count"] for b in hist_y) if isinstance(hist_y, list) else 0
print(f"  Yesterday total errors: {yesterday_total}")

# 2. GetHistograms for day before
print("Querying day-before histogram...")
hist_db = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
})
results['hist_day_before'] = hist_db
day_before_total = sum(b["count"] for b in hist_db) if isinstance(hist_db, list) else 0
print(f"  Day-before total errors: {day_before_total}")

# 3. Hourly distribution via SQL for yesterday
print("Querying yesterday hourly SQL...")
hourly_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "30",
})
results['hourly_yesterday'] = hourly_y
print(f"  Yesterday hourly entries: {len(hourly_y) if isinstance(hourly_y, list) else hourly_y}")

# 4. Hourly distribution via SQL for day before
print("Querying day-before hourly SQL...")
hourly_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    "line": "30",
})
results['hourly_day_before'] = hourly_db
print(f"  Day-before hourly entries: {len(hourly_db) if isinstance(hourly_db, list) else hourly_db}")

# 5. Top loggers for yesterday
print("Querying yesterday top loggers...")
loggers_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "30",
})
results['loggers_yesterday'] = loggers_y
print(f"  Yesterday logger entries: {len(loggers_y) if isinstance(loggers_y, list) else loggers_y}")

# 6. Top loggers for day before
print("Querying day-before top loggers...")
loggers_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    "line": "30",
})
results['loggers_day_before'] = loggers_db
print(f"  Day-before logger entries: {len(loggers_db) if isinstance(loggers_db, list) else loggers_db}")

# 7. Top error messages for yesterday
print("Querying yesterday top messages...")
msgs_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "30",
})
results['messages_yesterday'] = msgs_y
print(f"  Yesterday message entries: {len(msgs_y) if isinstance(msgs_y, list) else msgs_y}")

# 8. Top error messages for day before
print("Querying day-before top messages...")
msgs_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 20",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    "line": "30",
})
results['messages_day_before'] = msgs_db
print(f"  Day-before message entries: {len(msgs_db) if isinstance(msgs_db, list) else msgs_db}")

# 9. Version sampling for yesterday
print("Querying yesterday version...")
ver_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": YESTERDAY_FROM, "to": str(int(YESTERDAY_FROM) + 60),
    "line": "3",
})
results['version_yesterday'] = ver_y

# 10. Version sampling for day before
print("Querying day-before version...")
ver_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": DAY_BEFORE_FROM, "to": str(int(DAY_BEFORE_FROM) + 60),
    "line": "3",
})
results['version_day_before'] = ver_db

# 11. Keyword-based classification for yesterday
keywords = ["Dify", "DataCard", "角色不存在", "生成失败", "创建角色记录失败", "LingSmartClient", "Internal Server Error", "Already", "已经点赞", "孩子不属于你", "魔法正在施展中", "Exception in ASGI"]
kw_results_y = {}
for kw in keywords:
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f'level: ERROR and "{kw}"',
        "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    })
    total = sum(b["count"] for b in h) if isinstance(h, list) else 0
    kw_results_y[kw] = total

results['keywords_yesterday'] = kw_results_y

# 12. Keyword-based classification for day before
kw_results_db = {}
for kw in keywords:
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f'level: ERROR and "{kw}"',
        "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    })
    total = sum(b["count"] for b in h) if isinstance(h, list) else 0
    kw_results_db[kw] = total

results['keywords_day_before'] = kw_results_db

# 13. SQL for weapp_index messages (NoneType.stream)
print("Querying weapp_index errors...")
weapp_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and logger: app.controllers.weapp_index | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "20",
})
results['weapp_yesterday'] = weapp_y

# 14. SQL for task_scheduler error patterns
print("Querying task_scheduler patterns...")
ts_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and logger: app.utils.task_scheduler | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "20",
})
results['task_scheduler_yesterday'] = ts_y

# 15. signature_base count
print("Querying signature_base errors...")
sig_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and logger: app.middleware.signature_base | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "20",
})
results['signature_base_yesterday'] = sig_y

sig_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and logger: app.middleware.signature_base | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    "line": "20",
})
results['signature_base_day_before'] = sig_db

# 16. root logger analysis
print("Querying root logger...")
root_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "20",
})
results['root_yesterday'] = root_y

root_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and logger: root | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    "line": "20",
})
results['root_day_before'] = root_db

# 17. TTS-related errors
print("Querying TTS errors...")
tts_y = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and (logger: app.core.tts_client or logger: app.utils.audio_generator_scheduler) | SELECT count(1) as cnt, logger, substr(message, 1, 150) as msg_sample GROUP BY logger, msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "20",
})
results['tts_yesterday'] = tts_y

tts_db = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR and (logger: app.core.tts_client or logger: app.utils.audio_generator_scheduler) | SELECT count(1) as cnt, logger, substr(message, 1, 150) as msg_sample GROUP BY logger, msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": DAY_BEFORE_FROM, "to": DAY_BEFORE_TO,
    "line": "20",
})
results['tts_day_before'] = tts_db

# Write results
output_path = "/root/.hermes/workspace/sls_daily_2026-09-01.json"
with open(output_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)

print(f"\nAll results saved to {output_path}")
print(f"Summary: yesterday={yesterday_total}, day_before={day_before_total}")
