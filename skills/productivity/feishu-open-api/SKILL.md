---
name: feishu-open-api
category: productivity
description: Feishu/Lark Open API operations — messaging (send/receive/monitor), document/wiki management, and gateway troubleshooting. Covers tenant_access_token auth, IM messaging, wiki/doc copy, group message monitoring, and gateway event subscription debugging.
trigger: "User needs to interact with Feishu/Lark Open API — send messages, monitor groups, copy docs to wiki, troubleshoot gateway @mention issues, or manage Feishu app permissions."
---

# Feishu/Lark Open API

## Authentication (Shared)

All Feishu API calls require `tenant_access_token`:

```python
import urllib.request, json, yaml, os

# Read credentials from config
with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
    config = yaml.safe_load(f)
app_id = config['platforms']['feishu']['extra']['app_id']
app_secret = config['platforms']['feishu']['extra']['app_secret']

# Get token
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
req = urllib.request.Request(url, json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                             headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]
```

**Token expires in ~2 hours** — fetch fresh each time.

---

## Section 1: IM Messaging (from feishu-im-messaging)

### Sending Messages

**DM:**
```python
url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
body = {"receive_id": "ou_xxx", "msg_type": "text", "content": json.dumps({"text": "你好"})}
```

**Group Message with @Mention:**
```python
url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
body = {
    "receive_id": "oc_xxx",
    "msg_type": "text",
    "content": json.dumps({"text": '<at user_id="ou_xxx"></at> 你好。'})
}
```

**Find group chat_id**: `~/.hermes/channel_directory.json` → `platforms.feishu` array (look for `type: "group"`).

### Common Errors
| Code | Meaning |
|------|---------|
| `99991663` | Invalid/missing token — re-fetch |
| `230013` | Bot has NO availability — user never interacted with bot. **Fallback: group @mention** |
| `230001` | Chat not found — verify chat_id |

### Urgent Message (加急) — Three Endpoints

Feishu provides three urgent message APIs. All require `im:message.urgent` (app urgent) or `im:message.urgent.status:write` permissions. After sending a message, use the `message_id` from the response:

**1. 应用内加急 (In-app urgent) — No quota consumed:**
```python
msg_id = "om_xxx"  # from send response data.message_id
url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/urgent_app?user_id_type=open_id"
body = {"user_id_list": ["ou_xxx"]}  # open_ids to notify
req = urllib.request.Request(url, json.dumps(body).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    method="PATCH")
resp = json.loads(urllib.request.urlopen(req).read())
# {"code": 0, "data": {"invalid_user_id_list": []}, "msg": "success"}
```

**2. 短信加急 (SMS urgent) — Consumes SMS quota:**
`PATCH /open-apis/im/v1/messages/{message_id}/urgent_sms?user_id_type=open_id`

**3. 电话加急 (Phone urgent) — Consumes phone quota:**
`PATCH /open-apis/im/v1/messages/{message_id}/urgent_phone?user_id_type=open_id`

**⚠️ Pitfalls:**
- The old `/urgent` endpoint was **deprecated and removed** — it returns `404 page not found` (plain text, not JSON). Use `/urgent_app`, `/urgent_sms`, or `/urgent_phone` instead.
- `user_id_type=open_id` must be a **query parameter**, not in the request body.
- Body must use `{"user_id_list": ["ou_xxx"]}` — not `receive_id`.
- Method is **PATCH**, not POST.
- Can only urgent messages sent by the bot itself.
- Per-user unread urgent count max: 200.

### Message Format: Plain Text Only (⚠️ User Requirement)
**Feishu messages do NOT render Markdown.** `#`, `**`, `-`, `|` all display as raw characters.
- Use emoji prefixes (`• `, `1️⃣ `) instead of markdown lists
- Use plain text + blank lines instead of `#` headings
- Use key-value pairs instead of markdown tables

---

## Section 2: Message Monitoring (from feishu-im-message-monitor)

### Read Group Messages
```python
chat_id = "oc_xxx"
now_ms = int(time.time() * 1000)
start_ms = int((time.time() - 300) * 1000)  # 5 minutes ago

url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={chat_id}&start_time={start_ms}&end_time={now_ms}&page_size=50"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
resp = json.loads(urllib.request.urlopen(req).read())
items = resp.get("data", {}).get("items", [])
```

**⚠️ Timestamps must be in milliseconds, not seconds.** `end_time` must be >= `start_time` or error 230001.

### Detecting @all Messages
- **text**: `"@_all" in text` or `"@所有人" in text`
- **post**: `"at_all" in raw_json`
- **interactive (cards)**: `"@all" in raw_json` or `"@所有人" in raw_json`

### Conditional Monitoring with Cron
Use a detection script + cron job with `script` parameter. The script runs before the agent prompt, and its output is injected as context:
1. Create detection script at `~/.hermes/scripts/detect_at_all.py`
2. Create cron job with `script="detect_at_all.py"` and a prompt that acts on DETECTED/NO_DETECTED output

---

## Section 3: Wiki/Document Copy (from feishu-wiki-doc-copy)

### Correct Flow: Create Wiki Node → Write Blocks

**Step 1**: Create wiki node (this auto-creates the doc):
```python
wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{SPACE_ID}/nodes"
resp = api_post(wiki_url, token, {
    "parent_node_token": PARENT_NODE_TOKEN,
    "node_type": "origin",
    "obj_type": "docx",
    "title": title
})
doc_id = resp["data"]["node"]["obj_token"]  # Use THIS for writing blocks
```

**Step 2**: Write blocks in batches of 2, with 1.5s delay between batches:
```python
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
for i in range(0, len(blocks), 2):
    api_post(url, token, {"children": blocks[i:i+2]})
    time.sleep(1.5)
```

### ⚠️ Critical Pitfalls
1. **Wiki API ignores obj_token**: If you create a doc first, then try to use its ID as `obj_token` in the wiki API, the wiki API will IGNORE it and create a NEW empty doc. **Always create wiki node FIRST, then write to its returned `obj_token`.**
3. **text_run must use `content`, not `text`**: `{"text_run": {"content": "Hello"}}` ✅ — `{"text_run": {"text": "Hello"}}` ❌ (error 99992402)
4. **Block type 22 (bullet) fails**: Use `make_text("• item")` instead
5. **Emoji with variation selectors (1️⃣ 2️⃣ 3️⃣)**: The hidden U+FE0F bytes in emoji-number sequences are rejected by the write API. Use plain digits + regular emoji instead.
6. **Permission create: use `batch_create` not single**: `POST /permissions/{id}/members?type=docx` returns 1066001. Use `/members/batch_create?type=docx` with `{ "members": [...] }` array format.
7. **`member_type` valid values**: `email`, `openid`, `unionid`, `openchat`, `opendepartmentid`, `userid`, `groupid`, `wikispaceid`, `appid`. ⚠️ `openchatid` is NOT valid — use `openchat`. `group` is NOT valid — use `groupid`.
8. **Granting permission when user's open_id is unknown**: If contact API lacks permissions to resolve open_id, grant to the DM chat_id instead using `member_type: "openchat"`. Example: user DM chat_id `oc_xxx` → `{"member_type": "openchat", "member_id": "oc_xxx", "perm": "full_access"}`. This grants access to everyone in that DM (i.e., the user + bot).

### ⚠️ `mention_user` blocks cause 1770032 "forBidden"

When copying blocks from a template document that contains `mention_user` elements, the write API rejects them with `1770032 forBidden`. This happens because the bot cannot mention arbitrary users it doesn't have access to.

**Fix**: Convert `mention_user` elements to `text_run` before writing:

```python
def clean_block(block):
    clean = {k: v for k, v in block.items() if k not in ("block_id", "parent_id")}
    for key in ("heading1", "heading2", "heading3", "text"):
        if key in clean:
            elements = clean[key].get("elements", [])
            new_elements = []
            for elem in elements:
                if "mention_user" in elem:
                    # Replace mention_user with a text_run placeholder
                    mention = elem["mention_user"]
                    style = mention.get("text_element_style", {})
                    new_elements.append({
                        "text_run": {"content": "@用户", "text_element_style": style}
                    })
                else:
                    new_elements.append(elem)
            clean[key]["elements"] = new_elements
    return clean
```

Always clean blocks before writing: `clean_blocks = [clean_block(b) for b in raw_blocks]`.

### Copying Template Documents to Wiki — Correct Flow

The **ONLY** working flow for creating a wiki document with pre-populated content:

1. **Create wiki node first** → returns `obj_token` (auto-creates an empty doc)
2. **Clean template blocks** (remove `mention_user`, `block_id`, `parent_id`)
3. **Write blocks to the wiki node's `obj_token`**

**⚠️ Do NOT create a standalone doc via `/open-apis/docx/v1/documents` and then create a wiki node** — the wiki node creates its OWN empty doc, so your blocks go to a different document that nobody can find. The wiki API ignores `obj_token` in the create request, so you cannot attach an existing doc to a wiki node afterward.

```python
# ✅ Correct: wiki node first, then write to its obj_token
node = create_wiki_node(token, space_id, title)
doc_id = node["obj_token"]  # Use THIS for writing blocks
write_blocks(token, doc_id, clean_blocks)

# ❌ Wrong: standalone doc first — wiki node creates a separate empty doc
doc_id = create_standalone_doc(token)  # blocks go here
node = create_wiki_node(token, space_id, title)  # wiki points to a DIFFERENT empty doc
```

### Writing Blocks — Batch Size & Position

**Batch size**: 50 blocks per request works reliably in most cases. (Older guidance said max 2; larger batches are fine in practice.)

**⚠️ CRITICAL: block_type 2 uses `"text"`, NOT `"paragraph"`**: The Feishu docx API uses `"text"` as the key for paragraph blocks (block_type 2), not `"paragraph"`. Using `"paragraph"` always returns `1770001 "invalid param"`. This was confirmed by inspecting existing document blocks via the GET API — they return `"text"` as the field name.

```python
# ✅ Correct: use "text"
{"block_type": 2, "text": {"elements": [{"text_run": {"content": "Hello"}}]}}

# ❌ Wrong: "paragraph" is NOT the key name (always returns 1770001)
{"block_type": 2, "paragraph": {"elements": [{"text_run": {"content": "Hello"}}]}}
```

**⚠️ `urllib.request` vs `http.client` for docx writes**: When writing blocks, `urllib.request` may return `1770001` even with correct payloads. Use `http.client` directly — it works reliably:

```python
import http.client, json

conn = http.client.HTTPSConnection("open.feishu.cn")
conn.request("POST", f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
    json.dumps({"children": blocks}),
    {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"})
resp = json.loads(conn.getresponse().read().decode())
conn.close()
```

See `references/docx-block-write-failure.md` for the full debugging history.

**⚠️ "too deep level" error (1770005)**: When appending blocks using `position=after` with the last block's ID as the reference point, after many batches you hit this error. **Fix**: Always use `doc_id` as the parent block ID instead of nesting under the last written block:

```python
# ✅ Correct: always append as child of doc_id
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
for i in range(0, len(blocks), 50):
    batch = blocks[i:i+50]
    api_post(url, token, {"children": batch})
```

```python
# ❌ Wrong: chaining via last block ID eventually causes 1770005
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{last_block_id}/children?position=after"
```

### Clearing a Document Before Rewrite
The docx API does not support bulk replace. To clear content, paginate through all child blocks and delete individually:

```python
page_token = ""
all_ids = []
while True:
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=50"
    if page_token: url += f"&page_token={page_token}"
    resp = api_get(url, token)
    for item in resp["data"]["items"]:
        all_ids.append(item["block_id"])
    if not resp["data"].get("has_more"): break
    page_token = resp["data"]["page_token"]

for bid in all_ids:
    api_delete(f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{bid}", token)
```

### Bitable Parent Items Field Parsing
The `Parent items` (SingleLink) field returns a complex nested structure, not a simple record ID:

```json
{
  "record_ids": ["recvllEODjDIrG"],
  "table_id": "tbl9c4NAOuRuIPpt",
  "text": "父节点名称",
  "text_arr": ["父节点名称"],
  "type": "text"
}
```

**Resolution pattern**:
```python
parent_raw = fields.get("Parent items", [])
if parent_raw and isinstance(parent_raw, list) and len(parent_raw) > 0:
    p = parent_raw[0]
    if isinstance(p, dict):
        rec_ids = p.get("record_ids", [])
        parent_text = p.get("text", "")
        # Option A: use text directly (fast, but may be stale)
        parent_name = parent_text
        # Option B: resolve via record_ids (accurate, needs name_map lookup)
        if rec_ids and rec_ids[0] in name_map:
            parent_name = name_map[rec_ids[0]]
```

**Build name_map first**: Iterate all records before processing to create `{record_id: project_name}` mapping.

### Token Expiry (99991663)
`tenant_access_token` expires in ~2 hours. If you get code `99991663`, re-fetch via the auth endpoint. No retry will help — you must get a fresh token.

---

## Section 4: Gateway Troubleshooting (from feishu-gateway-troubleshoot)

### Group @Mentions Not Received

**Diagnostic Step 0**: Check event subscriptions (fastest):
```bash
TOKEN=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json' \
  -d '{"app_id":"APP_ID","app_secret":"APP_SECRET"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['tenant_access_token'])")

curl -s "https://open.feishu.cn/open-apis/application/v6/applications/APP_ID?lang=zh_cn" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
cb = d.get('data',{}).get('app',{}).get('callback_info',{})
print('Connection mode:', cb.get('callback_type'))
print('Subscribed callbacks:', cb.get('subscribed_callbacks', []))
"
```
- **If `im.message.receive_v1` NOT in `subscribed_callbacks`** → event subscription not published. Go to 飞书开放平台 → 事件订阅 → add `im.message.receive_v1` → publish new version.

### Root Causes (in order of likelihood)
1. **Event subscription not published** → `im.message.receive_v1` missing from `subscribed_callbacks`
2. **Missing permission** → `im:message.group_at_msg` not enabled in 权限管理
3. **Bot not in group** → Add bot via group settings. Test with: `POST /im/v1/messages?receive_id_type=chat_id`
4. **Bot identity not hydrated** → Missing `admin:app.info:readonly` permission. Warning at startup: `Unable to hydrate bot identity`
5. **Wrong bot @mentioned** → Multiple bots in group, user @mentions wrong one
6. **Code bug**: `group_policy` in config.yaml is ignored — only reads env var. Fix: patch `gateway/platforms/feishu.py` line ~1116 to read `extra.get("group_policy")`

### Hermes Agent Feishu Adapter Configuration Review

When asked about Hermes Agent's Feishu adapter config or to check for specific settings:

**Config locations** (in order):
1. `~/.hermes/config.yaml` → `feishu.enabled` and `feishu.extra.{domain, connection_mode, dm_policy, default_group_policy, group_policy, app_id, app_secret, bot_open_id}`
2. `~/.hermes/.env` → `FEISHU_ALLOW_ALL_USERS=true`
3. `~/.hermes/hermes-agent/cli-config.yaml.example` → reference template (no `feishu` section — Feishu is gateway-only)
4. `~/.hermes/hermes-agent/gateway/platforms/feishu.py` → adapter source (~4001 lines)

**Adapter settings dataclass** (`FeishuAdapterSettings` in feishu.py):
- `app_id`, `app_secret`, `domain_name`, `connection_mode` ("websocket" | "webhook")
- `encrypt_key`, `verification_token`
- `group_policy` ("open" | "allowlist" | "blacklist" | "admin_only" | "disabled")
- `allowed_group_users`, `bot_open_id`, `bot_user_id`, `bot_name`
- `dedup_cache_size`, `text_batch_delay_seconds`, `text_batch_max_messages`, `text_batch_max_chars`
- `webhook_host`, `webhook_port`, `webhook_path`
- `admins`, `default_group_policy`, `group_rules`

**⚠️ Key findings**:
- **No `reply_mode` config exists** in Hermes Agent — not in config.yaml, cli-config.yaml.example, or feishu.py source. Group reply behavior is controlled by `group_policy` / `default_group_policy` (open = respond to all, allowlist = only listed users, etc.).
- **No dedicated `feishu` section in cli-config.yaml.example** — Feishu is a gateway platform, not a CLI feature.
- **Adapter source path**: `~/.hermes/hermes-agent/gateway/platforms/feishu.py`

**Quick check commands**:
```python
# Check config.yaml for Feishu settings
import yaml
with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
    cfg = yaml.safe_load(f)
feishu = cfg.get('feishu', cfg.get('platforms', {}).get('feishu', 'Not found'))

# Check .env for FEISHU vars
with open(os.path.expanduser('~/.hermes/.env')) as f:
    env_lines = [l for l in f if 'FEISHU' in l.upper() or 'LARK' in l.upper()]

# Search adapter source for a specific key
import subprocess
result = subprocess.run(['grep', '-n', 'reply_mode', '~/.hermes/hermes-agent/gateway/platforms/feishu.py'], capture_output=True, text=True)
```

### Key Permissions Required
| Permission | Purpose |
|------------|---------|
| `im:message.group_at_msg` | Receive group @mention messages |
| `im.message.receive_v1` | Event subscription for incoming messages (both DM and group) |
| `admin:app.info:readonly` | Auto-hydrate bot identity for mention gating |
| `docs:permission.member` | Share documents with groups |

### Known Chat IDs
| Purpose | Chat ID |
|---------|---------|
| Alert source group | `oc_1876881e2b07f5b3b4ecc29189ae8217` |
| Report target group | `oc_611b7861968a34f8c2f538f67410b629` |
