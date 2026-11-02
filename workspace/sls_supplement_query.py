#!/usr/bin/env python3
"""Supplementary SLS queries for deeper analysis."""
import sys, os, json, time
from datetime import datetime, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"
QUERY = "level: ERROR"

now = datetime.now()
yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)
day_before_start = yesterday_start - timedelta(days=1)
day_before_end = yesterday_start - timedelta(seconds=1)

y_from = str(int(yesterday_start.timestamp()))
y_to = str(int(yesterday_end.timestamp()))
d_from = str(int(day_before_start.timestamp()))
d_to = str(int(day_before_end.timestamp()))

client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1)
client.ensure_daemon_running()
time.sleep(1)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
assert resp.get("status") == "success", f"Failed: {resp}"

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def sql_agg(query, from_ts, to_ts):
    return call_sls("GetLogs", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": f"{QUERY} | {query}",
        "from": from_ts, "to": to_ts, "line": "50", "region": REGION,
    })

def histogram_total(query, from_ts, to_ts):
    h = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
    })
    return sum(b.get("count", 0) for b in h) if isinstance(h, list) else 0

results = {}

# 1. Error messages by weapp_index (NoneType.stream breakdown)
weapp_msgs = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE logger='app.controllers.weapp_index' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["weapp_index_msgs"] = weapp_msgs if isinstance(weapp_msgs, list) else []

# 2. exception_handlers messages
eh_msgs = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE logger='app.exception_handlers' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["exception_handlers_msgs"] = eh_msgs if isinstance(eh_msgs, list) else []

# 3. root logger messages detailed
root_msgs = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE logger='root' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    y_from, y_to)
results["root_msgs_detailed"] = root_msgs if isinstance(root_msgs, list) else []

# 4. voip logger messages
voip_msgs = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE logger='app.controllers.voip' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["voip_msgs"] = voip_msgs if isinstance(voip_msgs, list) else []

# 5. Keyword: 创作记录不存在 (yesterday)
results["chuangzuo_y"] = histogram_total(f'{QUERY} and "创作记录不存在"', y_from, y_to)

# 6. Keyword: 辩论 (yesterday)
results["debate_y"] = histogram_total(f'{QUERY} and "辩论"', y_from, y_to)

# 7. Keyword: Duplicate entry (yesterday)
results["duplicate_y"] = histogram_total(f'{QUERY} and "Duplicate entry"', y_from, y_to)

# 8. Keyword: utf-8 / surrogate (yesterday)
results["surrogate_y"] = histogram_total(f'{QUERY} and "utf-8"', y_from, y_to)

# 9. Keyword: require subscribe (yesterday)
results["subscribe_y"] = histogram_total(f'{QUERY} and "require subscribe"', y_from, y_to)

# 10. coze messages
coze_msgs = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE logger='app.controllers.coze' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["coze_msgs"] = coze_msgs if isinstance(coze_msgs, list) else []

# 11. Dify-related for yesterday (SQL-based since keyword failed)
dify_msgs_y = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE message like '%Dify%' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["dify_msgs_y"] = dify_msgs_y if isinstance(dify_msgs_y, list) else []

# 12. Debate for yesterday (SQL)
debate_msgs_y = sql_agg(
    "SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample WHERE message like '%辩论%' GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["debate_msgs_y"] = debate_msgs_y if isinstance(debate_msgs_y, list) else []

# 13. voip errors breakdown (HTTP 500 vs TaskConflict vs ServiceUnavailable)
voip_detail = sql_agg(
    "SELECT count(1) as cnt, regexp_extract(message, '(ResourceAllocationFailed|ServiceUnavailable|TaskConflict|InternalError|voip call has been exist)', 1) as error_type WHERE logger='app.controllers.voip' GROUP BY error_type ORDER BY cnt DESC LIMIT 10",
    y_from, y_to)
results["voip_detail"] = voip_detail if isinstance(voip_detail, list) else []

# Save
out_path = "/root/.hermes/workspace/sls_supplement_2026-09-06.json"
with open(out_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"Saved to {out_path}")
