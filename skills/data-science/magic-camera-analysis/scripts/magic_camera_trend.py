#!/usr/bin/env python3
"""Query magic camera (child_custom_role_task type=2) data for last N days.
Usage: python3 -c "import sys; sys.argv=['hermes_cli/main.py']; exec(open('scripts/magic_camera_trend.py').read())" --days 7
"""
import socket, json, sys, os
from datetime import datetime, timedelta

def send_request(action, **kwargs):
    sock_path = "/tmp/hermes-rds-daemon.sock"
    with open(os.path.expanduser("~/.hermes/rds/.daemon-token")) as f:
        auth_token = f.read().strip()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)
    msg = json.dumps({"action": action, "auth_token": auth_token, **kwargs})
    sock.sendall(msg.encode() + b"\n")
    data = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk: break
        data += chunk
        if b"\n" in data: break
    sock.close()
    return json.loads(data.strip())

days = 7
for arg in sys.argv[1:]:
    if arg.startswith("--days="):
        days = int(arg.split("=")[1])

today = datetime.now()
send_request("register_caller")

totals = {"total": 0, "success": 0, "fail": 0, "users": 0}

print(f"{'日期':<12} {'总任务':<8} {'成功':<8} {'失败':<8} {'活跃用户':<10} {'成功率':<8}")
print("-" * 64)

for i in range(days - 1, -1, -1):
    d = today - timedelta(days=i)
    date_str = d.strftime("%Y-%m-%d")
    sql = f"""SELECT CAST(date AS CHAR) as dt, COUNT(*) as total,
        COUNT(CASE WHEN status=2 THEN 1 END) as success,
        COUNT(CASE WHEN status=3 THEN 1 END) as fail,
        COUNT(DISTINCT child_id) as active_users
    FROM child_custom_role_task WHERE type=2 AND date = '{date_str}' GROUP BY date"""
    resp = send_request("execute_sql", connection_id="lingos_new", sql=sql, params={})
    if resp.get("status") == "success" and resp["data"]["rows"]:
        r = resp["data"]["rows"][0]
        t, s, f, u = int(r.get("total",0)), int(r.get("success",0)), int(r.get("fail",0)), int(r.get("active_users",0))
        rate = round(s/t*100, 1) if t > 0 else 0
        print(f"{date_str:<12} {t:<8} {s:<8} {f:<8} {u:<10} {rate}%")
        totals["total"] += t; totals["success"] += s; totals["fail"] += f; totals["users"] += u
    else:
        print(f"{date_str:<12} {'0':<8} {'0':<8} {'0':<8} {'0':<10} 0%")

print("-" * 64)
all_rate = round(totals["success"]/totals["total"]*100, 1) if totals["total"] > 0 else 0
print(f"{'合计':<12} {totals['total']:<8} {totals['success']:<8} {totals['fail']:<8} {totals['users']:<10} {all_rate}%")
