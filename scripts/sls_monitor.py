#!/usr/bin/env python3
"""SLS 告警监控：检测飞书群 @all 消息，分析 SLS 日志并推送到目标群"""

import urllib.request, json, time, os

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
SOURCE_CHAT_ID = "oc_1876881e2b07f5b3b4ecc29189ae8217"
TARGET_CHAT_ID = "oc_611b7861968a34f8c2f538f67410b629"

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())
    if resp.get("code") != 0:
        raise Exception(f"Token 失败: {resp}")
    return resp["tenant_access_token"]

def feishu_api(token, url, data=None):
    req = urllib.request.Request(url, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data).encode()
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def get_messages(token, minutes=5):
    now_ms = int(time.time() * 1000)
    start_ms = int((time.time() - minutes * 60) * 1000)
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={SOURCE_CHAT_ID}&start_time={start_ms}&end_time={now_ms}&page_size=50"
    resp = feishu_api(token, url)
    return resp.get("data", {}).get("items", [])

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

def send_message(token, text):
    content = json.dumps({"text": text})
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    data = {"receive_id": TARGET_CHAT_ID, "msg_type": "text", "content": content}
    return feishu_api(token, url, data)

def main():
    print("开始 SLS 告警监控...")
    token = get_feishu_token()
    
    messages = get_messages(token, minutes=5)
    print(f"获取到 {len(messages)} 条消息")
    
    at_all_msgs = [m for m in messages if has_at_all(m)]
    if not at_all_msgs:
        print("未检测到 @all，跳过")
        return
    
    print(f"检测到 {len(at_all_msgs)} 条 @all 消息")
    result = send_message(token, "🚨 检测到 @all 告警，正在分析 SLS 日志...")
    print(f"已发送通知: {json.dumps(result, ensure_ascii=False)}")

if __name__ == "__main__":
    main()
