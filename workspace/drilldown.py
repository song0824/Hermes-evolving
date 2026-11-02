#!/usr/bin/env python3
"""Drill-down query for specific loggers."""
import sys, os, time
sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient
from datetime import datetime, timedelta, timezone

client = DaemonClient()
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(2)
client.ensure_daemon_running()
time.sleep(2)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
print(f"Register: {resp}")

cst = timezone(timedelta(hours=8))
Y_FROM = str(int(datetime(2026,8,8,0,0,0,tzinfo=cst).timestamp()))
Y_TO = str(int(datetime(2026,8,8,23,59,59,tzinfo=cst).timestamp()))

def call(action, params):
    try:
        return client.execute_aliyun_api(
            ak_id="sls服务端和客户端日志", product="sls", api_action=action,
            params=params, region="cn-shanghai"
        ).get("data", {})
    except Exception as e:
        return {"_error": str(e)}

loggers = [
    "root",
    "app.controllers.weapp_index",
    "app.controllers.voip",
    "app.core.tts_client",
    "app.core.video_generator",
    "app.exception_handlers",
    "app.service.butterfiy_hatch",
    "app.utils.audio_generator_scheduler",
]

for logger in loggers:
    print(f"\n=== {logger} ===")
    q = f"level: ERROR and logger: {logger} | SELECT count(1) as cnt, substr(message, 1, 200) as m GROUP BY m ORDER BY cnt DESC LIMIT 10"
    r = call("GetLogs", {
        "project": "leap-online", "logstore": "ling-server",
        "query": q, "from": Y_FROM, "to": Y_TO, "line": "20", "region": "cn-shanghai"
    })
    if isinstance(r, list):
        for x in r:
            print(f"  [{x.get('cnt',0)}x] {x.get('m','')[:100]}")
    else:
        print(f"  {r}")

print("\n=== DONE ===")
