#!/usr/bin/env python3
"""Query SLS logs for '角色不存在' samples."""
import sys
sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")

from rds_security_plugin.daemon_client import DaemonClient
import json

client = DaemonClient()

AK_ID = "sls服务端和客户端日志"

def call_sls_api(action, params, region="cn-shanghai"):
    """Call SLS API through the daemon."""
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID,
            product="sls",
            api_action=action,
            params=params,
            region=region,
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

# Step 1: List credentials
print("=== Step 1: List AKSK Credentials ===")
try:
    creds = client.list_aksk()
    print(json.dumps(creds, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error listing credentials: {e}")
print()

# Step 2: GetLogs for "角色不存在"
print("=== Step 2: GetLogs for '角色不存在' ===")
resp = call_sls_api("GetLogs", {
    "project": "leap-online",
    "logstore": "ling-server",
    "query": "level: ERROR and 角色不存在",
    "from": "1779368400",
    "to": "1779379199",
    "line": "3",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
