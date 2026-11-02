#!/usr/bin/env python3
"""Day before drill-down for comparison."""
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

cst = timezone(timedelta(hours=8))
D_FROM = str(int(datetime(2026,8,7,0,0,0,tzinfo=cst).timestamp()))
D_TO = str(int(datetime(2026,8,7,23,59,59,tzinfo=cst).timestamp()))

def call(action, params):
    try:
        return client.execute_aliyun_api(
            ak_id="sls服务端和客户端日志", product="sls", api_action=action,
            params=params, region="cn-shanghai"
        ).get("data", {})
    except Exception as e:
        return {"_error": str(e)}

# Check butterfiy_hatch existence day before
print("=== butterfiy_hatch day before ===")
r = call("GetLogs", {
    "project": "leap-online", "logstore": "ling-server",
    "query": "level: ERROR and logger: app.service.butterfiy_hatch",
    "from": D_FROM, "to": D_TO, "line": "5", "region": "cn-shanghai"
})
print(f"  Result: {r if not isinstance(r, list) else f'{len(r)} entries'}")

# Check weapp_family_base
print("\n=== weapp_family_base yesterday ===")
Y_FROM = str(int(datetime(2026,8,8,0,0,0,tzinfo=cst).timestamp()))
Y_TO = str(int(datetime(2026,8,8,23,59,59,tzinfo=cst).timestamp()))
r = call("GetLogs", {
    "project": "leap-online", "logstore": "ling-server",
    "query": "level: ERROR and logger: app.controllers.weapp_family_base | SELECT count(1) as cnt, substr(message,1,200) as m GROUP BY m ORDER BY cnt DESC LIMIT 10",
    "from": Y_FROM, "to": Y_TO, "line": "20", "region": "cn-shanghai"
})
if isinstance(r, list):
    for x in r: print(f"  [{x.get('cnt',0)}x] {x.get('m','')[:100]}")
else: print(f"  {r}")

# CDN 400 errors
print("\n=== CDN 400 errors yesterday ===")
r = call("GetHistograms", {
    "project": "leap-online", "logstore": "ling-server",
    "query": "level: ERROR and 下载图片失败",
    "from": Y_FROM, "to": Y_TO,
})
cdn_y = sum(b.get("count",0) for b in r) if isinstance(r, list) else 0
print(f"  Yesterday: {cdn_y}")

r = call("GetHistograms", {
    "project": "leap-online", "logstore": "ling-server",
    "query": "level: ERROR and 下载图片失败",
    "from": D_FROM, "to": D_TO,
})
cdn_d = sum(b.get("count",0) for b in r) if isinstance(r, list) else 0
print(f"  Day Before: {cdn_d}")

# voip HTTP 500 TaskConflict
print("\n=== voip TaskConflict (HTTP 500) yesterday ===")
r = call("GetHistograms", {
    "project": "leap-online", "logstore": "ling-server",
    "query": "level: ERROR and voip and HTTP 500",
    "from": Y_FROM, "to": Y_TO,
})
voip500_y = sum(b.get("count",0) for b in r) if isinstance(r, list) else 0
print(f"  Yesterday HTTP 500: {voip500_y}")

r = call("GetHistograms", {
    "project": "leap-online", "logstore": "ling-server",
    "query": "level: ERROR and voip and HTTP 500",
    "from": D_FROM, "to": D_TO,
})
voip500_d = sum(b.get("count",0) for b in r) if isinstance(r, list) else 0
print(f"  Day Before HTTP 500: {voip500_d}")

print("\n=== DONE ===")
