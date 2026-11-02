#!/usr/bin/env python3
"""Query SLS error logs for ling-server daily report."""
import sys
sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")

from rds_security_plugin.daemon_client import DaemonClient
import json

client = DaemonClient()
client.ensure_daemon_running()

AK_ID = "sls服务端和客户端日志"

# Timestamps
YESTERDAY_FROM = "1779292800"
YESTERDAY_TO = "1779379199"
DAYBEFORE_FROM = "1779206400"
DAYBEFORE_TO = "1779292799"

PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

def call_sls(action, params, ak_id=AK_ID, product="sls", region=REGION):
    try:
        result = client.execute_aliyun_api(
            ak_id=ak_id,
            product=product,
            api_action=action,
            params=params,
            region=region,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

# Step 1: List credentials
print("=== Listing AKSK Credentials ===")
try:
    creds = client.list_aksk()
    print(json.dumps(creds, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
print()

# Query 1: GetHistograms yesterday
print("=== QUERY_HISTOGRAM_YESTERDAY ===")
resp = call_sls("GetHistograms", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": YESTERDAY_FROM,
    "to": YESTERDAY_TO,
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 2: GetHistograms day-before
print("=== QUERY_HISTOGRAM_DAYBEFORE ===")
resp = call_sls("GetHistograms", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": DAYBEFORE_FROM,
    "to": DAYBEFORE_TO,
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 3: GetLogs - top error loggers yesterday
print("=== QUERY_LOGGERS_YESTERDAY ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": YESTERDAY_FROM,
    "to": YESTERDAY_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 4: GetLogs - top error loggers day-before
print("=== QUERY_LOGGERS_DAYBEFORE ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": DAYBEFORE_FROM,
    "to": DAYBEFORE_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 5: GetLogs - top error messages yesterday
print("=== QUERY_MESSAGES_YESTERDAY ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": YESTERDAY_FROM,
    "to": YESTERDAY_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 6: GetLogs - top error messages day-before
print("=== QUERY_MESSAGES_DAYBEFORE ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 150) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 15",
    "from": DAYBEFORE_FROM,
    "to": DAYBEFORE_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 7: GetLogs - error count by hour yesterday
print("=== QUERY_HOURLY_YESTERDAY ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": YESTERDAY_FROM,
    "to": YESTERDAY_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 8: GetLogs - error count by hour day-before
print("=== QUERY_HOURLY_DAYBEFORE ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": DAYBEFORE_FROM,
    "to": DAYBEFORE_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 9: GetLogs - error distribution by errcode yesterday
print("=== QUERY_ERRCODE_YESTERDAY ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, regexp_extract(message, 'errno[^0-9]*([0-9]+)', 1) as errcode GROUP BY errcode ORDER BY cnt DESC LIMIT 15",
    "from": YESTERDAY_FROM,
    "to": YESTERDAY_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

# Query 10: GetLogs - error distribution by errcode day-before
print("=== QUERY_ERRCODE_DAYBEFORE ===")
resp = call_sls("GetLogs", {
    "project": PROJECT,
    "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, regexp_extract(message, 'errno[^0-9]*([0-9]+)', 1) as errcode GROUP BY errcode ORDER BY cnt DESC LIMIT 15",
    "from": DAYBEFORE_FROM,
    "to": DAYBEFORE_TO,
    "powerSql": "true",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
print()

print("=== ALL QUERIES COMPLETE ===")
