#!/usr/bin/env python3
"""
技术周会文档自动复制脚本
每周五 9:00 运行，从模板复制文档到 wiki 空间并通知群
"""
import urllib.request
import http.client
import json
import yaml
import os
import time
from datetime import datetime

CONFIG_PATH = os.path.expanduser("~/.hermes/config.yaml")
TEMPLATE_DOC = "KtOLd1e7CoSXkNxgF7jcDiI7nrd"
WIKI_SPACE_ID = "7612892588537892047"
NOTIFY_GROUP = "oc_611b7861968a34f8c2f538f67410b629"
TARGET_USER = "ou_b1ae70c2ac573b88db4656fcd79482e2"  # 愚者


def get_token():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    app_id = config["platforms"]["feishu"]["extra"]["app_id"]
    app_secret = config["platforms"]["feishu"]["extra"]["app_secret"]
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req = urllib.request.Request(
        url,
        json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]


def feishu_post(token, path, body_dict, method="POST"):
    body = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
    conn = http.client.HTTPSConnection("open.feishu.cn")
    conn.request(
        method,
        path,
        body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    raw = conn.getresponse().read().decode()
    conn.close()
    return json.loads(raw)


def feishu_get(token, path):
    conn = http.client.HTTPSConnection("open.feishu.cn")
    conn.request("GET", path, headers={"Authorization": f"Bearer {token}"})
    raw = conn.getresponse().read().decode()
    conn.close()
    return json.loads(raw)


def clean_block(block):
    """清理 block，移除 block_id、parent_id，替换 mention_user 为 text_run"""
    clean = {k: v for k, v in block.items() if k not in ("block_id", "parent_id")}
    # 处理 mention_user → text_run
    for key in ("heading1", "heading2", "heading3", "text"):
        if key in clean:
            elements = clean[key].get("elements", [])
            new_elements = []
            for elem in elements:
                if "mention_user" in elem:
                    mention = elem["mention_user"]
                    style = mention.get("text_element_style", {})
                    new_elements.append(
                        {
                            "text_run": {
                                "content": "@用户",
                                "text_element_style": style,
                            }
                        }
                    )
                else:
                    new_elements.append(elem)
            clean[key]["elements"] = new_elements
    return clean


def get_template_blocks(token):
    all_blocks = []
    page_token = ""
    while True:
        path = f"/open-apis/docx/v1/documents/{TEMPLATE_DOC}/blocks/{TEMPLATE_DOC}/children?page_size=50"
        if page_token:
            path += f"&page_token={page_token}"
        resp = feishu_get(token, path)
        items = resp.get("data", {}).get("items", [])
        all_blocks.extend(items)
        if not resp["data"].get("has_more"):
            break
        page_token = resp["data"]["page_token"]
    return all_blocks


def create_doc(token, title):
    resp = feishu_post(token, "/open-apis/docx/v1/documents", {"folder_token": ""})
    if resp.get("code") != 0:
        raise Exception(f"Create doc failed: {resp}")
    return resp["data"]["document"]["document_id"]


def write_blocks(token, doc_id, blocks):
    url = f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    batch_size = 30
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i : i + batch_size]
        resp = feishu_post(token, url, {"children": batch})
        if resp.get("code") != 0:
            raise Exception(
                f"Write blocks batch {i} failed: code={resp.get('code')} msg={resp.get('msg')}"
            )
        time.sleep(0.5)


def create_wiki_node(token, space_id, title, obj_token):
    resp = feishu_post(
        token,
        f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
        {
            "node_type": "origin",
            "obj_type": "docx",
            "title": title,
        },
    )
    if resp.get("code") != 0:
        raise Exception(f"Create wiki node failed: {resp}")
    return resp["data"]["node"]


def grant_permission(token, doc_id, user_open_id):
    """Grant full_access to user on the doc"""
    resp = feishu_post(
        token,
        f"/open-apis/drive/v1/permissions/{doc_id}/members/batch_create?type=docx",
        {
            "members": [
                {
                    "member_type": "openid",
                    "member_id": user_open_id,
                    "perm": "full_access",
                }
            ]
        },
    )
    return resp


def send_group_message(token, chat_id, text):
    resp = feishu_post(
        token,
        "/open-apis/im/v1/messages?receive_id_type=chat_id",
        {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        },
    )
    return resp


def main():
    token = get_token()
    week_str = datetime.now().strftime("%Y-%m-%d")
    title = f"技术周会 {week_str}"

    print(f"[1/6] Creating document...")
    doc_id = create_doc(token, title)
    print(f"  Doc ID: {doc_id}")

    print(f"[2/6] Fetching template blocks...")
    raw_blocks = get_template_blocks(token)
    print(f"  Got {len(raw_blocks)} blocks")

    print(f"[3/6] Cleaning and writing blocks...")
    clean_blocks = [clean_block(b) for b in raw_blocks]
    write_blocks(token, doc_id, clean_blocks)
    print(f"  Wrote {len(clean_blocks)} blocks")

    print(f"[4/6] Creating wiki node...")
    node = create_wiki_node(token, WIKI_SPACE_ID, title, doc_id)
    wiki_url = node.get("url", "")
    print(f"  Wiki URL: {wiki_url}")

    print(f"[5/6] Granting permission to 愚者...")
    perm_resp = grant_permission(token, doc_id, TARGET_USER)
    print(f"  Permission result: {perm_resp.get('code')}")

    print(f"[6/6] Sending notification to group...")
    msg = f"📋 技术周会文档已创建\n\n📅 {week_str}\n🔗 {wiki_url}\n\n请各负责人填写本周进展。"
    msg_resp = send_group_message(token, NOTIFY_GROUP, msg)
    if msg_resp.get("code") == 0:
        msg_id = msg_resp["data"]["message_id"]
        # Add urgent notification
        feishu_post(
            token,
            f"/open-apis/im/v1/messages/{msg_id}/urgent_app?user_id_type=open_id",
            {"user_id_list": [TARGET_USER]},
            method="PATCH",
        )
        print(f"  Message sent + urgent to 愚者")
    else:
        print(f"  Message send failed: {msg_resp}")

    print(f"\nDone! Wiki URL: {wiki_url}")
    return wiki_url


if __name__ == "__main__":
    main()
