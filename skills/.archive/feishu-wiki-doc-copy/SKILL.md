---
name: feishu-wiki-doc-copy
description: 通过飞书 Open API 复制模板文档到知识库，创建每周技术周会文档。总结了 API 的多个坑和正确做法。
category: productivity
---

# 飞书 Wiki 文档复制 - 坑与正确做法

## 场景
从一个模板文档（docx）复制内容到知识库（wiki）中，创建新的周报文档。也适用于从零创建独立文档并写入内容。

## 从零创建独立文档（非 Wiki 节点）
当不需要将文档放入 wiki 知识库时，直接创建文档：
```python
doc_url = "https://open.feishu.cn/open-apis/docx/v1/documents"
resp = api_post(doc_url, token, {"folder_token": "", "title": "文档标题"})
doc_id = resp["data"]["document"]["document_id"]
# 然后按 Step 4 写入 blocks
```
`folder_token` 传空字符串即可，返回的 `document_id` 就是写入 blocks 时用的 doc_id。

## 正确流程（已验证 2026-05-29）

### Step 1: 获取 tenant_access_token
```python
url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
req = urllib.request.Request(url, json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                             headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
token = resp["tenant_access_token"]
```

### Step 2: 获取源文档 blocks
```python
def get_blocks(token, doc_id):
    all_items = []
    page_token = ""
    while True:
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks?document_id={doc_id}&page_size=500"
        if page_token:
            url += "&page_token=" + page_token
        resp = api_get(url, token)
        items = resp.get('data', {}).get('items', [])
        all_items.extend(items)
        if not resp.get('data', {}).get('has_more', False):
            break
        page_token = resp.get('data', {}).get('page_token', '')
    return all_items
```

### Step 3: 创建 wiki 节点（⚠️ 关键！）
```python
wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{SPACE_ID}/nodes"
resp = api_post(wiki_url, token, {
    "parent_node_token": PARENT_NODE_TOKEN,
    "node_type": "origin",
    "obj_type": "docx",
    "title": title
})
node_token = resp["data"]["node"]["node_token"]
obj_token = resp["data"]["node"]["obj_token"]  # 这是飞书自动生成的文档 ID
```

### Step 4: 写入 blocks
```python
doc_id = obj_token  # 用 Step 3 返回的 obj_token
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"

batch_size = 2
for i in range(0, len(writeable), batch_size):
    batch = writeable[i:i+batch_size]
    api_post(url, token, {"children": batch})
    time.sleep(1.5)
```

## ⚠️ 踩过的坑

### 坑 1: wiki 节点 API 忽略传入的 obj_token
**错误做法**：先创建文档 → 拿到 doc_id → 再创建 wiki 节点传 obj_token
```python
# ❌ 错误：wiki API 会忽略 obj_token，自己创建一个空文档
doc_id = create_document(token, title)  # 拿到 doc_id
wiki_api_post(token, {"obj_token": doc_id, ...})  # 被忽略！wiki 会新建一个空文档
# 结果：你写的 blocks 到旧 doc_id 里，用户看到的是 wiki 新建的空文档
```

**正确做法**：先创建 wiki 节点（obj_type=docx），wiki 会自动创建文档并返回 obj_token，然后写入内容到这个 obj_token
```python
# ✅ 正确：先 wiki → 再写内容
wiki_resp = wiki_api_post(token, {"obj_type": "docx", "title": title})
doc_id = wiki_resp["data"]["node"]["obj_token"]  # 用 wiki 返回的
write_blocks(token, doc_id, blocks)
```

### 坑 2: text_run 字段必须用 content 而非 text
**错误写法**（返回 code=99992402, "field validation failed"）：
```python
{"text_run": {"text": "Hello", "style": {}}}  # ❌ text 字段不被识别
```
**正确写法**：
```python
{"text_run": {"content": "Hello", "style": {}}}  # ✅ 必须用 content
```
API 报错信息：`children[*].text.elements[*].text_run.content is required`。任何 block 类型（paragraph/heading/bullet/ordered）中的 text_run 都必须用 `content` 字段。

### 坑 2b: mention_user 元素写入
飞书 API **支持**写入 mention_user 元素，但需要特殊处理：
```python
# ✅ 支持
{"mention_user": {"user_id": "ou_xxx"}}

# ❌ 不支持的写法（会导致元素丢失）
# 直接复制源文档的 mention_user 对象时，要确保只保留 user_id 字段
```

### 坑 3: Batch 写入限制
- 每次最多 **2 个 blocks**
- 批次间需要 **1.5s 延迟**
- 遇到 429 需要重试（sleep 2s）

### 坑 4: Block 类型转换
- **Divider (type=21)** 不可通过 API 创建，需替换为空文本或分隔线文本
- **mention_doc** 写入时替换为 `[文档]` 文本
- 每个 block 必须保留 `style` 字段：`{"align": 1, "folded": false}`

### 坑 6: API 请求方法
当传入 `data` 参数时，即使 method="GET"，实际应为 POST：
```python
if data is not None:
    data = json.dumps(data).encode('utf-8')
    actual_method = "POST"  # 不要信任传入的 method 参数
```

## 读取文档（含图片提取）

通过 `docx/v1/documents/{doc_id}/blocks` 获取文档内容。文档中的图片不是子 block，而是直接挂在 block 对象上（尤其是 Grid block type=27）。图片下载使用 drive API，详见 `references/feishu-doc-image-download.md`。

## 完整脚本参考
`~/.hermes/scripts/weekly_tech_meeting.py`

## 速查表
权限端点、Block 类型映射、URL 格式见 `references/feishu-docx-api-reference.md`。
