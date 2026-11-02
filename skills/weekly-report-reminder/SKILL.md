---
name: weekly-report-reminder
description: 每周一 11:00 自动检查技术周会知识库中的最新周报文档，分析谁未填写，并 @ 未填写的人发送到研发运维群。
category: productivity
---

# 技术周会周报催填任务

## ⚠️ 节假日检查（最高优先级）

**执行任何操作前，先检查当天是否为中国法定节假日。**

节假日日期列表见 `references/china-holidays.md`。使用方式：

```python
from datetime import date

# 复制 CHINA_HOLIDAYS 集合和 is_china_holiday() 函数，或从 references/china-holidays.md 引用
today = date.today().isoformat()
if today in CHINA_HOLIDAYS:
    print("SKIP|今天是法定节假日，不发送催填消息")
    exit()
```

**如果今天是法定节假日，输出 `SKIP|...` 后直接终止，不执行后续任何操作，不发送任何消息。**

## 任务流程

### 1. 获取凭证
从 `~/.hermes/config.yaml` 读取 Feishu App ID 和 Secret，或用已知的：
- App ID: `cli_a97b1e4633f99cb0`
- App Secret: `${FEISHU_APP_SECRET}`
获取 `tenant_access_token`。

### 2. 定位知识库和最新周报文档
知识库 wiki token: `AAGlw95lZi4sUqk78vzc7mkHnIb`

```python
# 1. 获取 token
token = get_tenant_access_token()

# 2. 解析 wiki 节点获取 space_id 和 node_token
node_url = f'https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?obj_type=wiki&token=AAGlw95lZi4sUqk78vzc7mkHnIb'
node_resp = api_get(node_url, token)
space_id = node_resp['data']['node']['space_id']
node_token = node_resp['data']['node']['node_token']

# 3. 列出 wiki 子节点
children_url = f'https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?parent_node_token={node_token}&page_size=50'
children_resp = api_get(children_url, token)
items = children_resp.get('data', {}).get('items', [])

# 4. 按文档标题中的日期排序（YYYY年M月D日格式），而不是 obj_edit_time
import re
def extract_date_from_title(title):
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', title)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return '0000-00-00'
items.sort(key=lambda x: extract_date_from_title(x.get('title', '')), reverse=True)

# ⚠️ 最新文档可能返回 404（应用未被添加为协作者）
# 必须遍历文档，找到第一个 raw_content/blocks API 可访问的
doc_id = None
doc_title = None
doc_node_token = None
doc_url = None

for item in items:
    test_doc_id = item['obj_token']
    raw_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{test_doc_id}/raw_content?document_id={test_doc_id}'
    try:
        resp = api_get(raw_url, token)
        if resp and resp.get('code') == 0 and resp.get('data', {}).get('content'):
            doc_id = test_doc_id
            doc_title = item['title']
            doc_node_token = item['node_token']
            doc_url = f"https://ta1mz8n1mps.feishu.cn/wiki/{doc_node_token}"
            print(f"✅ Found accessible doc: {doc_title}")
            break
        else:
            print(f"⚠️ Doc {item['title']} returned empty/no content, trying next...")
    except Exception as e:
        print(f"⚠️ Doc {item['title']} inaccessible ({e}), trying next...")

if not doc_id:
    raise RuntimeError("No accessible weekly report document found")
```

### 3. 读取文档内容并分析谁未填写
```python
import json, urllib.request

# 获取 raw_content（包含 @ 人名顺序和文本内容）
raw_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/raw_content?document_id={doc_id}'
raw_resp = api_get(raw_url, token)
content = raw_resp.get('data', {}).get('content', '')

lines = content.split('\n')

# 找到所有 @ 开头的人名
name_order = []
for line in lines:
    line = line.strip()
    if line.startswith('@'):
        name = line[1:].strip()
        if '|' in name:
            name = name.split('|')[0].strip()
        name_order.append(name)

# 检查每个人下面是否有内容（直到下一个 @ 或 "本周整体周报总结"）
filled = []
unfilled = []

for i, name in enumerate(name_order):
    search_name = '@' + name
    start_idx = None
    for j, line in enumerate(lines):
        ls = line.strip()
        if ls == search_name or ls.startswith(search_name + '|'):
            start_idx = j
            break
    
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        l = lines[j].strip()
        if l.startswith('@') or '本周整体' in l or '本周工作进展' in l:
            end_idx = j
            break
    
    content_lines = [l for l in lines[start_idx+1:end_idx] if l.strip()]
    
    if content_lines:
        filled.append(name)
    else:
        unfilled.append(name)
```

### 4. 发送 @ 催填消息到研发运维群
目标群: `oc_611b7861968a34f8c2f538f67410b629`

需要用 blocks API 获取 uid 来构建 `<at>` 标签：

```python
# 获取 blocks 来映射 uid
blocks_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks?document_id={doc_id}&page_size=500'
blocks_resp = api_get(blocks_url, token)
all_items = blocks_resp.get('data', {}).get('items', [])

# 构建 name -> uid 映射
name_uid_map = {}
for item in all_items:
    if item.get('block_type') == 5:  # h3
        for el in item.get('heading3', {}).get('elements', []):
            if 'mention_user' in el:
                uid = el['mention_user'].get('user_id', '')
                # 从 raw_content 中找对应名字
                # 需要按顺序匹配
                break

# 更可靠的方式：按顺序匹配 raw_content 中的 @ 顺序和 blocks 中的 H3 顺序
raw_names = []  # 从 raw_content 提取
block_uids = [] # 从 blocks H3 提取
for i in range(min(len(raw_names), len(block_uids))):
    name_uid_map[raw_names[i]] = block_uids[i]

# 构建消息
at_tags = ''
for name in unfilled:
    uid = name_uid_map.get(name, '')
    if uid:
        at_tags += f'<at user_id="{uid}">{name}</at>'

message_text = f"{at_tags}\n\n📋 技术周会周报催填\n\n还有 {len(unfilled)} 位同学未填写周报，请尽快补充～\n\n📄 文档链接：{doc_url}\n\n✅ 已填写（{len(filled)}人）：{', '.join(filled)}"

# 发送消息
send_url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id'
data = json.dumps({
    "receive_id": "oc_611b7861968a34f8c2f538f67410b629",
    "msg_type": "text",
    "content": json.dumps({"text": message_text})
}).encode()

req = urllib.request.Request(send_url, data=data, method='POST')
req.add_header('Authorization', f'Bearer {token}')
req.add_header('Content-Type', 'application/json; charset=utf-8')
resp = api_post(req)
```

### 5. 输出结果
在 cron 输出中打印谁未填写、谁已填写，并确认消息已发送。

## 注意事项
- ⚠️ **最新文档可能返回 404**：飞书 docx API 要求应用被添加为文档协作者才能访问。如果 wiki 节点 API 能列出文档但 `raw_content`/`blocks` 返回 HTTP 404，说明应用未被添加为该文档的协作者。**解决方案**：遍历排序后的文档列表，找到第一个 API 可访问的文档使用（见步骤 2 的 fallback 代码）。
- 飞书 raw_content API 返回纯文本，适合提取 @ 顺序
- blocks API 返回结构化数据，含 mention_user 的 uid，用于构建 @ 标签
- 必须用两个 API 结合：raw_content 判断是否填写，blocks 获取 uid
- 消息类型为 text，content 是 JSON 字符串
- 目标群：oc_611b7861968a34f8c2f538f67410b629（研发运维群）
- 知识库 wiki token：AAGlw95lZi4sUqk78vzc7mkHnIb
- App ID: cli_a97b1e4633f99cb0, Secret: ${FEISHU_APP_SECRET}
