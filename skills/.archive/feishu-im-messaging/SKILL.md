---
name: feishu-im-messaging
description: Send messages via Feishu/Lark Open API — handles DMs, group @mentions, and token management.
trigger: User asks to send a Feishu message, mention someone, or interact with Feishu IM API.
---

## Authentication & Token

1. **Extract credentials** from `~/.hermes/config.yaml`:
   - `platforms.feishu.extra.app_id`
   - `platforms.feishu.extra.app_secret`
2. **Get tenant_access_token** (use Python to avoid bash quoting issues):
```python
import urllib.request, json
app_id, app_secret = "cli_xxx", "xxx"
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
req = urllib.request.Request(url, json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                             headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]
```

## Sending Messages

### Direct Message (DM)
```python
url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
body = {"receive_id": "ou_xxx", "msg_type": "text", "content": json.dumps({"text": "你好"})}
```

### Group Message with @Mention
If DM fails with error `230013` ("Bot has NO availability to this user"), fall back to sending in a group chat with an @mention.

1. **Find group chat_id** from `~/.hermes/channel_directory.json` → `platforms.feishu` array (look for `type: "group"`).
2. **Send with @mention**:
```python
url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
body = {
    "receive_id": "oc_xxx",
    "msg_type": "text",
    "content": json.dumps({"text": '<at user_id="ou_xxx"></at> 你好。'})
}
```

## Common Errors
- `99991663`: Invalid/missing token — re-fetch token.
- `230013`: Bot has NO availability — user never interacted with bot or isn't in same group. **Fallback: group @mention.**
- `230001`: Chat not found — verify chat_id.

## Message Format: Plain Text Only (⚠️ 用户明确要求)
**飞书消息不支持任何 Markdown 渲染。** `#`、`**`、`-` 列表、`|` 表格等全部显示为原始字符。用户已明确反馈"markdown 的格式都没能正确显示"，要求以后全部用纯文本。

### 禁止使用的 Markdown 语法
- `# 标题` → 用纯文本标题 + 空行分隔
- `**粗体**` → 用 Emoji 或直接写文字
- `- 列表项` → 用 `• ` 或 `1️⃣ ` 等 Emoji 前缀
- `| 表头 | 内容 |` → 用逐行键值对或纯文本对齐

### 正确格式示例
```
📊 核心数据

总任务数: 3,592 (↑ +160.1%)
生成成功: 3,377 (↑ +159.4%)
成功率: 94.0% (↓ -0.3pp)

━━━━━━━━━━━━━━━━━━━━

🔥 热门项目

Ribbita — FDV $110.9M
加密货币+Fintech 融合

aixbt — FDV $22.2M
加密市场的 Bloomberg，AI 驱动的市场情报 Agent

━━━━━━━━━━━━━━━━━━━━

🔑 总结

1️⃣ 有身份和钱包
2️⃣ 能工作赚钱
3️⃣ 能被投资和交易
```

## Notes
- Always use Python's `urllib` or `requests` for API calls; bash `curl` with nested JSON is error-prone.
- Token expires in ~2 hours; fetch fresh each time.
- `channel_directory.json` is maintained by Hermes and contains known Feishu group chat_ids.
