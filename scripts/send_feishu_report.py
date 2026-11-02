#!/usr/bin/env python3
"""发送AI硬件日报到飞书群"""
import urllib.request, json, yaml, ssl

with open('/root/.hermes/config.yaml') as f:
    config = yaml.safe_load(f)

feishu_config = config.get('feishu', config.get('platforms', {}).get('feishu', {}))
extra = feishu_config.get('extra', feishu_config)
app_id = extra['app_id']
app_secret = extra['app_secret']

ctx = ssl.create_default_context()
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
req = urllib.request.Request(url, json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                             headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req, context=ctx).read())["tenant_access_token"]

today = "2026-10-09"

report_lines = [
    "AI硬件行业日报 | " + today,
    "",
    "1. 微软发布Nvidia RTX Spark芯片AI PC，同步升级Windows 11",
    "微软在旧金山活动上公布了基于Nvidia RTX Spark芯片的AI PC具体规格与定价，包括Surface Laptop Ultra等新品。这些设备专为运行本地AI模型和智能体设计，标志着Windows AI PC生态的重要推进。",
    "https://techcrunch.com/2026/10/07/microsoft-releases-new-nvidia-chip-ai-pcs-with-revamped-windows-11/",
    "",
    "2. 人形机器人数据初创公司Mecka AI获红杉6000万美元融资",
    "Mecka AI通过付费收集和分析人类日常活动动作数据，用于训练人形机器人及其他类型机器人。其核心思路是：高质量的真人动作数据是具身智能机器人落地的关键瓶颈。",
    "https://techcrunch.com/2026/10/08/mecka-ai-funding-sequoia/",
    "",
    "3. Nvidia押注物理AI：目标打造更安全的无人出租车与人形机器人",
    "Nvidia正大力投入物理AI（Physical AI）领域，通过Cosmos世界基础模型和Isaac机器人仿真平台，推动自动驾驶和人形机器人的安全部署。其策略是用仿真+真实数据闭环加速具身智能落地。",
    "https://arstechnica.com/ai/2026/10/nvidias-big-bet-on-physical-ai-aims-for-safer-robotaxis-humanoid-robots/",
    "",
    "4. Natura推出99美元AI智能戒指，将智能体戴在手指上",
    "Natura发布Interface智能戒指，支持通过手势唤出AI智能体完成任务、记录想法和控制设备，同时具备健康监测功能。99美元的定价大幅降低了AI可穿戴设备的门槛。",
    "https://techcrunch.com/2026/10/08/naturas-99-smart-ring-puts-ai-agents-on-your-finger/",
    "",
    "5. Google发布离线AI会议助手Edge Foresight，对标Granola",
    "Google推出基于本地AI的Edge Foresight应用，可在设备端完成会议录音转写、笔记生成和问答，无需云端连接。这体现了Google在端侧AI算力上的布局策略。",
    "https://techcrunch.com/2026/10/08/google-releases-a-new-local-first-granola-competitor/",
    "",
    "---",
    "今日洞察：AI硬件三大趋势 -- Nvidia RTX Spark推动AI PC普及、具身智能（人形机器人+物理AI）成为资本与技术双重热点、端侧AI可穿戴设备加速下沉到消费级市场。",
]

report = "\n".join(report_lines)

send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
body = {
    "receive_id": "oc_8b8978c0510660ec4da3c52ebc7bb9a3",
    "msg_type": "text",
    "content": json.dumps({"text": report})
}
req = urllib.request.Request(send_url, json.dumps(body).encode(),
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
resp = json.loads(urllib.request.urlopen(req, context=ctx).read())
print("发送结果: " + json.dumps(resp, ensure_ascii=False))
print("")
print("=" * 60)
print("最终简报内容：")
print("=" * 60)
print(report)
