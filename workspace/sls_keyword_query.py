#!/usr/bin/env python3
"""SLS keyword histogram queries for error categorization + sample logs."""
import sys, os, json, time
from datetime import datetime, timedelta

sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.12/site-packages")
from rds_security_plugin.daemon_client import DaemonClient

AK_ID = "sls服务端和客户端日志"
PROJECT = "leap-online"
LOGSTORE = "ling-server"
REGION = "cn-shanghai"

now = datetime.now()
yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
day_before_start = yesterday_start - timedelta(days=1)
yesterday_from = str(int(yesterday_start.timestamp()))
yesterday_to = str(int((yesterday_start + timedelta(days=1) - timedelta(seconds=1)).timestamp()))
day_before_from = str(int(day_before_start.timestamp()))
day_before_to = str(int((yesterday_start - timedelta(seconds=1)).timestamp()))

# ── Daemon restart ──────────────────────────────────────────────────────
client = DaemonClient()
print("Killing existing daemon...")
os.system("pkill -9 -f hermes-rds-daemon 2>/dev/null")
time.sleep(1.5)
print("Starting fresh daemon...")
client.ensure_daemon_running()
time.sleep(1.5)
resp = client.send_request({"action": "register_caller"}, timeout_s=5)
assert resp.get("status") == "success", f"Failed to register: {resp}"

def call_sls(action, params):
    try:
        result = client.execute_aliyun_api(
            ak_id=AK_ID, product="sls", api_action=action,
            params=params, region=REGION,
        )
        return result.get("data", {})
    except Exception as e:
        return {"_error": str(e)}

def get_hist_count(query, from_ts, to_ts):
    hist = call_sls("GetHistograms", {
        "project": PROJECT, "logstore": LOGSTORE,
        "query": query, "from": from_ts, "to": to_ts,
    })
    if isinstance(hist, list):
        return sum(b.get("count", 0) for b in hist)
    return 0

results = {}

# ── Keyword histograms for yesterday ────────────────────────────────────
keywords_yesterday = {}
keywords_day_before = {}

keyword_queries = [
    ("Internal Server Error", "level: ERROR and Internal Server Error"),
    ("No response returned", "level: ERROR and No response returned"),
    ("magic_rate_limit", "level: ERROR and 魔法正在施展中"),
    ("tts_error", "level: ERROR and TTS转换异常"),
    ("ling_smart_fail", "level: ERROR and Cannot connect to host ling-smart"),
    ("wallpaper_error", "level: ERROR and WALLPAPER_ERROR"),
    ("energy_fail", "level: ERROR and 获取用户能量失败"),
    ("suggestion_keyerror", "level: ERROR and 签名验证异常"),
    ("child_not_yours", "level: ERROR and 孩子不属于你"),
    ("role_not_exist", "level: ERROR and 角色不存在"),
    ("Unhandled_500", "level: ERROR and Unhandled Internal Server Error"),
    ("ASGI_exception", "level: ERROR and Exception in ASGI application"),
    ("task_timeout", "level: ERROR and 超时"),
    ("debate_error", "level: ERROR and 辩论"),
    ("QueuePool", "level: ERROR and QueuePool"),
    ("video_timeout", "level: ERROR and 视频转换"),
    ("risk_control", "level: ERROR and 风控"),
    ("uvicorn_error", "level: ERROR and logger: uvicorn.error"),
]

print("\n=== Keyword histograms ===")
for name, query in keyword_queries:
    y_count = get_hist_count(query, yesterday_from, yesterday_to)
    d_count = get_hist_count(query, day_before_from, day_before_to)
    keywords_yesterday[name] = y_count
    keywords_day_before[name] = d_count
    print(f"  {name}: yesterday={y_count}, day_before={d_count}")

results["keywords_yesterday"] = keywords_yesterday
results["keywords_day_before"] = keywords_day_before

# ── Sample logs for exception analysis (peak hour) ─────────────────────
# Peak hour was 15:00 CST = 07:00 UTC
# 15:00 CST on 2026-05-30 = 07:00 UTC = 1780099200 to 1780102800
print("\n=== Sample logs (yesterday peak hour 15:00 CST) ===")
peak_from = "1780102800"  # 15:00 CST
peak_to = "1780106400"    # 16:00 CST

# Actually let me use 14:30-16:30 CST which maps to the 599-count bucket
# 14:30 CST = 06:30 UTC = 1780097400
# 16:00 CST = 08:00 UTC = 1780102800
sample_logs = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": "1780097400", "to": "1780102800",
    "line": "5", "region": REGION,
})
if isinstance(sample_logs, list):
    print(f"  Got {len(sample_logs)} samples")
    for i, log in enumerate(sample_logs[:5], 1):
        logger = log.get("logger", "?")
        message = log.get("message", "?")[:120]
        exception = log.get("exception", "?")[:120]
        print(f"  [{i}] logger={logger}")
        print(f"      message={message}")
        print(f"      exception={exception}")
        print()
results["peak_samples"] = sample_logs

# ── Day-before peak hour samples ────────────────────────────────────────
print("\n=== Day-before peak hour samples ===")
# Day-before peak was 04:00 CST = 20:00 UTC prev day = 1779991200
sample_logs2 = call_sls("GetLogs", {
    "project": PROJECT, "logstore": LOGSTORE,
    "query": "level: ERROR",
    "from": "1779991200", "to": "1779998400",
    "line": "5", "region": REGION,
})
if isinstance(sample_logs2, list):
    print(f"  Got {len(sample_logs2)} samples")
    for i, log in enumerate(sample_logs2[:5], 1):
        logger = log.get("logger", "?")
        message = log.get("message", "?")[:120]
        exception = log.get("exception", "?")[:120]
        print(f"  [{i}] logger={logger}")
        print(f"      message={message}")
        print(f"      exception={exception}")
        print()
results["day_before_peak_samples"] = sample_logs2

# Save
with open("/root/.hermes/workspace/sls_keyword_analysis.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print("\nSaved to /root/.hermes/workspace/sls_keyword_analysis.json")
print("DONE")
