#!/usr/bin/env python3
"""检测源群最近 5 分钟是否有 @all 消息"""
import urllib.request, json, time, os

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
SOURCE_CHAT_ID = "oc_1876881e2b07f5b3b4ecc29189ae8217"

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp.get("tenant_access_token", "")

def get_messages(token, minutes=5):
    now_ms = int(time.time() * 1000)
    start_ms = int((time.time() - minutes * 60) * 1000)
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={SOURCE_CHAT_ID}&start_time={start_ms}&end_time={now_ms}&page_size=50"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        return result.get("data", {}).get("items", [])
    except:
        return []

def has_at_all(item):
    msg_type = item.get("msg_type", "")
    content_raw = item.get("body", {}).get("content", "")
    if msg_type == "text":
        content = json.loads(content_raw) if content_raw else {}
        text = content.get("text", "")
        return "@_all" in text or "@所有人" in text or "@all" in text
    elif msg_type == "post":
        content = json.loads(content_raw) if content_raw else {}
        raw = json.dumps(content, ensure_ascii=False)
        return "at_all" in raw or "@_all" in raw
    return False

token = get_feishu_token()
messages = get_messages(token, minutes=5)
at_all_msgs = [m for m in messages if has_at_all(m)]

if at_all_msgs:
    for m in at_all_msgs:
        ct = m.get("create_time", "")
        sender = m.get("sender", {})
        content = m.get("body", {}).get("content", "")
        print(f"DETECTED_AT_ALL: time={ct}, sender={sender.get('id','')}, content={content[:200]}")
else:
    print("NO_AT_ALL_DETECTED")
