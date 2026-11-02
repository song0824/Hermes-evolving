#!/usr/bin/env python3
"""
Daily SLS Error Log Analysis Report Generator
Queries ling-server Error logs for yesterday (2026-05-22) and day before (2026-05-21)
"""
import sys
import json
import os

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")

from rds_security_plugin.daemon_client import DaemonClient

client = DaemonClient()
AK_ID = "sls服务端和客户端日志"

# Timestamps
YESTERDAY_FROM = "1779379200"  # 2026-05-22 00:00:00 CST
YESTERDAY_TO = "1779465599"    # 2026-05-22 23:59:59 CST
DAYBEFORE_FROM = "1779292800"  # 2026-05-21 00:00:00 CST
DAYBEFORE_TO = "1779379199"    # 2026-05-21 23:59:59 CST

PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

def call_sls(action, params):
    """Call SLS API through the daemon."""
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID,
            product="sls",
            api_action=action,
            params=params,
            region=REGION,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

results = {}

# Step 1: GetHistograms for yesterday
print("Step 1: GetHistograms for yesterday (2026-05-22)...")
results["hist_yesterday"] = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
})
print(f"  Done. Keys: {list(results['hist_yesterday'].keys()) if isinstance(results['hist_yesterday'], dict) else type(results['hist_yesterday'])}")

# Step 2: GetHistograms for day before
print("Step 2: GetHistograms for day before (2026-05-21)...")
results["hist_daybefore"] = call_sls("GetHistograms", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
})
print(f"  Done.")

# Step 3: Top loggers yesterday
print("Step 3: Top loggers yesterday...")
results["loggers_yesterday"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "50", "region": REGION,
})
print(f"  Done.")

# Step 4: Top loggers day before
print("Step 4: Top loggers day before...")
results["loggers_daybefore"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, logger GROUP BY logger ORDER BY cnt DESC LIMIT 20",
    "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
    "line": "50", "region": REGION,
})
print(f"  Done.")

# Step 5: Top error messages yesterday
print("Step 5: Top error messages yesterday...")
results["messages_yesterday"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "50", "region": REGION,
})
print(f"  Done.")

# Step 6: Top error messages day before
print("Step 6: Top error messages day before...")
results["messages_daybefore"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, substr(message, 1, 200) as msg_sample GROUP BY msg_sample ORDER BY cnt DESC LIMIT 10",
    "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
    "line": "50", "region": REGION,
})
print(f"  Done.")

# Step 7: Hourly distribution yesterday
print("Step 7: Hourly distribution yesterday...")
results["hourly_yesterday"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "50", "region": REGION,
})
print(f"  Done.")

# Step 8: Hourly distribution day before
print("Step 8: Hourly distribution day before...")
results["hourly_daybefore"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR | SELECT count(1) as cnt, date_format(from_unixtime(__time__ + 28800), '%H:00') as hour GROUP BY hour ORDER BY hour",
    "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
    "line": "50", "region": REGION,
})
print(f"  Done.")

# Step 9: Sample errors yesterday
print("Step 9: Sample errors yesterday...")
results["sample_yesterday"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": YESTERDAY_FROM, "to": YESTERDAY_TO,
    "line": "10", "region": REGION,
})
print(f"  Done.")

# Step 10: Sample errors day before
print("Step 10: Sample errors day before...")
results["sample_daybefore"] = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": DAYBEFORE_FROM, "to": DAYBEFORE_TO,
    "line": "10", "region": REGION,
})
print(f"  Done.")

# Save all results
output_path = "/root/.hermes/workspace/sls_ling_server_error_data_2026-05-22.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\nAll data saved to {output_path}")
print("Script complete.")
