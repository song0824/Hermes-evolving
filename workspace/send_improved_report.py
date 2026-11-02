#!/usr/bin/env python3
"""Send improved AI hardware daily report to Feishu with proper Chinese summaries."""

import urllib.request
import os
import json
from datetime import datetime

app_id = "cli_a97b1e4633f99cb0"
app_secret = os.environ.get("FEISHU_APP_SECRET", "")
chat_id = "oc_8b8978c0510660ec4da3c52ebc7bb9a3"

# Get token
auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
auth_req = urllib.request.Request(
    auth_url,
    json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
    headers={"Content-Type": "application/json"}
)
auth_resp = json.loads(urllib.request.urlopen(auth_req, timeout=10).read())
token = auth_resp.get("tenant_access_token", "")

today = datetime.now().strftime('%Y-%m-%d')

# Top 5 AI hardware news with proper Chinese summaries
news_items = [
    {
        "emoji": "1️⃣",
        "title": "苹果起诉OpenAI窃取硬件商业机密",
        "summary": "苹果指控OpenAI唆使被挖角员工携带机密演示文稿、秘密原型机及关键供应商信息跳槽，双方在AI硬件领域的竞争升级。",
        "url": "https://www.wired.com/story/apple-sues-openai-allegedly-stealing-ip-hardware/",
        "source": "Wired"
    },
    {
        "emoji": "2️⃣",
        "title": "人形机器人公司拟通过SPAC上市",
        "summary": "一家人形机器人企业宣布借壳上市计划，但其CEO坦言短期内无法实现\"机器人进家庭\"的愿景，反映行业仍处早期阶段。",
        "url": "https://techcrunch.com/2026/07/05/this-humanoid-robotics-company-is-going-public-but-its-ceo-isnt-promising-a-robot-in-your-home-anytime-soon/",
        "source": "TechCrunch Robotics"
    },
    {
        "emoji": "3️⃣",
        "title": "Sam Altman太空数据中心计划遭业内质疑",
        "summary": "OpenAI CEO提议在太空建设AI数据中心以解决能源和散热问题，但多数专家认为这在当前技术条件下不切实际。",
        "url": "https://techcrunch.com/2026/07/13/sam-altmans-space-data-center-trash-talk-is-what-most-experts-already-believe/",
        "source": "TechCrunch AI"
    },
    {
        "emoji": "4️⃣",
        "title": "机器人手公司和解特斯拉诉讼并完成1100万美元融资",
        "summary": "一家专注于机器人灵巧手研发的公司与特斯拉达成商业机密诉讼和解，同时宣布完成1100万美元新一轮融资。",
        "url": "https://techcrunch.com/2026/06/29/robot-hand-company-settles-tesla-trade-secret-suit-and-announces-11m-raise/",
        "source": "TechCrunch Robotics"
    },
    {
        "emoji": "5️⃣",
        "title": "量子纠错技术实现处理器持续自动校准",
        "summary": "Ars Technica报道，最新量子纠错技术可实现量子处理器的持续动态重新校准，这是量子计算硬件走向实用的重要突破。",
        "url": "https://arstechnica.com/science/2026/07/quantum-error-correction-can-constantly-recalibrate-a-processor/",
        "source": "Ars Technica"
    }
]

lines = []
lines.append(f"🤖 AI硬件行业日报 | {today}")
lines.append("")

for item in news_items:
    lines.append(f"{item['emoji']} {item['title']}")
    lines.append(f"📌 {item['summary']}")
    lines.append(f"🔗 {item['url']}")
    lines.append(f"📰 来源: {item['source']}")
    lines.append("")

lines.append("💡 今日洞察：AI硬件赛道全面升温——从人形机器人IPO、量子计算突破到Apple与OpenAI的硬件专利战，AI的底层算力与载体正成为科技巨头争夺的核心战场。")

msg = "\n".join(lines)
print(msg)

# Send message
send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
body = {
    "receive_id": chat_id,
    "msg_type": "text",
    "content": json.dumps({"text": msg})
}
send_req = urllib.request.Request(
    send_url,
    json.dumps(body).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
)
send_resp = json.loads(urllib.request.urlopen(send_req, timeout=10).read())
print(f"\n发送结果: {json.dumps(send_resp, ensure_ascii=False, indent=2)}")

if send_resp.get("code") == 0:
    print("✅ 消息发送成功！")
else:
    print(f"❌ 发送失败: {send_resp}")
