#!/usr/bin/env python3
"""Call SLS API through the RDS daemon."""
import json
import sys

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")

from rds_security_plugin.daemon_client import DaemonClient

client = DaemonClient()

AK_ID = "sls服务端和客户端日志"


def call_sls_api(action, params):
    """Call SLS API through the daemon."""
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID,
            product="sls",
            api_action=action,
            params=params,
            region="cn-shanghai",
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def main() -> None:
    print("=== Step 1: List AKSK Credentials ===")
    try:
        creds = client.list_aksk()
        print(json.dumps(creds, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error listing credentials: {e}")
    print()

    print("=== Step 2: GetHistograms ===")
    resp = call_sls_api("GetHistograms", {
        "project": "leap-online",
        "logstore": "ling-server",
        "query": "level: ERROR",
        "from": "1779368400",
        "to": "1779379199",
    })
    print(json.dumps(resp, indent=2, ensure_ascii=False))
    print()

    print("=== Step 3: GetLogs ===")
    resp2 = call_sls_api("GetLogs", {
        "project": "leap-online",
        "logstore": "ling-server",
        "query": "level: ERROR | select message, count(*) as cnt group by message order by cnt desc limit 20",
        "from": "1779368400",
        "to": "1779379199",
        "line": "100",
    })
    print(json.dumps(resp2, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
