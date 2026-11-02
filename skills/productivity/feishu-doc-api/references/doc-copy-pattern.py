#!/usr/bin/env python3
"""Feishu 文档从模板复制的参考实现。
模式：读取源文档所有 blocks → 创建新文档 → 写入 blocks → 添加到 wiki → 开通权限。
"""
import json
import urllib.request
import urllib.error
import time
import os

def get_token():
    # 从 ~/.hermes/config.yaml 读取 app_id / app_secret
    # 或直接使用已知的凭证
    import yaml
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    app_id = config["platforms"]["feishu"]["extra"]["app_id"]
    app_secret = config["platforms"]["feishu"]["extra"]["app_secret"]
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req = urllib.request.Request(url, json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read(), strict=False)["tenant_access_token"]

def api_request(url, token, data=None, method="GET"):
    """⚠️ 关键：如果 data 不为 None，urllib 会自动改用 POST 方法。
    必须显式指定 method="POST" 当有 data 时，或者让函数自动推导。"""
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        if isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')
        actual_method = "POST"
    else:
        actual_method = method

    req = urllib.request.Request(url, data=data, method=actual_method, headers=headers)

    for retry in range(3):
        try:
            resp = urllib.request.urlopen(req)
            return json.loads(resp.read().decode('utf-8'), strict=False)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8')
            if e.code == 429 and retry < 2:
                time.sleep(2)
                continue
            raise Exception(f"API Error {e.code}: {body}")
    return None

def get_document_blocks(token, doc_id):
    """分页获取文档所有 blocks"""
    all_items = []
    page_token = ""
    while True:
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks?document_id={doc_id}&page_size=500"
        if page_token:
            url += "&page_token=" + page_token
        resp = api_request(url, token)
        all_items.extend(resp.get('data', {}).get('items', []))
        if not resp.get('data', {}).get('has_more', False):
            break
        page_token = resp.get('data', {}).get('page_token', '')
    return all_items

def blocks_to_writeable(blocks, root_id):
    """将源 blocks 转为可写入格式（排除根 block，跳过不可创建的 divider）"""
    writeable = []
    content_fields = ["text", "heading1", "heading2", "heading3", "heading4",
                     "heading5", "heading6", "heading7", "heading8", "heading9",
                     "bullet", "ordered", "code", "quote", "todo", "callout", "equation"]
    for block in blocks:
        if block.get('block_id') == root_id:
            continue
        bt = block.get('block_type', 0)
        if bt == 21:  # Divider 不可创建
            writeable.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": "---"}}]}})
            continue
        new_block = {"block_type": bt}
        for field in content_fields:
            if field in block:
                new_block[field] = block[field]
                break
        if not any(f in new_block for f in content_fields):
            new_block["text"] = {"elements": [{"text_run": {"content": ""}}]}
        writeable.append(new_block)
    return writeable

def create_document(token, title):
    resp = api_request("https://open.feishu.cn/open-apis/docx/v1/documents", token, data={"title": title})
    return resp["data"]["document"]["document_id"]

def write_blocks(token, doc_id, blocks):
    for i in range(0, len(blocks), 2):
        batch = blocks[i:i+2]
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        api_request(url, token, data={"children": batch})
        time.sleep(1.5)

def add_to_wiki(token, space_id, parent_node_token, doc_id):
    url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    return api_request(url, token, data={
        "parent_node_token": parent_node_token,
        "node_type": "origin",
        "obj_token": doc_id,
        "obj_type": "docx"
    })

def grant_permission(token, doc_id, chat_id):
    url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/members/batch_create?type=docx"
    return api_request(url, token, data={
        "members": [{"member_type": "openchat", "member_id": chat_id, "perm": "full_access"}]
    })
