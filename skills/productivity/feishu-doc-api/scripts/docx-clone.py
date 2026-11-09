#!/usr/bin/env python3
"""
Clone a Feishu docx document into a wiki space as a child node.
Proven pattern 2026-05-29.

Usage: python docx-clone.py <app_id> <app_secret> <src_doc_id> <space_id> <parent_node_token> <title>
Or import as module and call clone_document().
"""
import json
import urllib.request
import urllib.error
import time
import sys
from datetime import datetime


def get_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req = urllib.request.Request(url, json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                                 headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read(), strict=False)
    return resp["tenant_access_token"]


def api_post(url, token, data):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, body, method='POST')
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    for retry in range(3):
        try:
            resp = urllib.request.urlopen(req)
            return json.loads(resp.read().decode('utf-8'), strict=False)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            if e.code == 429 and retry < 2:
                time.sleep(2)
                continue
            raise Exception(f"HTTP {e.code}: {err_body}")
    return None


def api_get(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode('utf-8'), strict=False)


def get_source_blocks(token, doc_id):
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


def convert_block(block):
    bt = block.get('block_type', 0)
    if bt == 21:  # divider — NOT creatable via API
        return {"block_type": 2, "text": {"elements": [{"text_run": {"content": "---"}}]}}

    new_block = {"block_type": bt}
    content_fields = ["text", "heading1", "heading2", "heading3", "heading4",
                     "heading5", "heading6", "heading7", "heading8", "heading9",
                     "bullet", "ordered", "code", "quote", "todo", "callout", "equation"]

    for field in content_fields:
        if field in block:
            src = block[field]
            new_elements = []
            for el in src.get("elements", []):
                if "text_run" in el:
                    new_elements.append(el)
                elif "mention_user" in el:
                    new_elements.append({"mention_user": {"user_id": el["mention_user"]["user_id"]}})
                elif "mention_doc" in el:
                    new_elements.append({"text_run": {"content": "[文档]"}})
                else:
                    new_elements.append(el)
            new_block[field] = {
                "elements": new_elements,
                "style": src.get("style", {"align": 1, "folded": False})
            }
            break

    if not any(f in new_block for f in content_fields):
        new_block["text"] = {"elements": [{"text_run": {"content": ""}}]}
    return new_block


def clone_document(token, src_doc_id, space_id, parent_node_token, title, chat_id=None):
    # 1. Get source blocks
    blocks = get_source_blocks(token, src_doc_id)
    writeable = [convert_block(b) for b in blocks if b.get('block_type', 0) != 1]

    # 2. Create wiki node FIRST (API auto-creates document — do NOT pre-create docx)
    wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    resp = api_post(wiki_url, token, {
        "parent_node_token": parent_node_token,
        "node_type": "origin",
        "obj_type": "docx",
        "title": title
    })
    node = resp["data"]["node"]
    doc_id = node["obj_token"]
    node_token = node["node_token"]

    # 3. Write blocks (batch_size=2, 1.5s sleep)
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    for i in range(0, len(writeable), 2):
        batch = writeable[i:i+2]
        api_post(url, token, {"children": batch})
        time.sleep(1.5)

    # 4. Grant permission (best-effort — app may lack docs:permission.member)
    if chat_id:
        try:
            perm_url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_id}/members/batch_create?type=docx"
            api_post(perm_url, token, {
                "members": [{"member_type": "openchat", "member_id": chat_id, "perm": "full_access"}]
            })
        except:
            pass

    return {
        "doc_id": doc_id,
        "node_token": node_token,
        "url": f"https://open.feishu.cn/wiki/{node_token}"
    }


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: docx-clone.py <app_id> <app_secret> <src_doc_id> <space_id> <parent_node_token> [title] [chat_id]")
        sys.exit(1)

    app_id, app_secret, src_doc_id, space_id, parent_node_token = sys.argv[1:6]
    title = sys.argv[6] if len(sys.argv) > 6 else f"Cloned {datetime.now():%Y-%m-%d}"
    chat_id = sys.argv[7] if len(sys.argv) > 7 else None

    token = get_token(app_id, app_secret)
    result = clone_document(token, src_doc_id, space_id, parent_node_token, title, chat_id)
    print(f"Created: {result['url']}")
    print(f"doc_id: {result['doc_id']}")
