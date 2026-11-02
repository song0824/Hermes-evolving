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
import re
from datetime import datetime

CONFIG_PATH = os.path.expanduser("~/.hermes/config.yaml")
TEMPLATE_DOC = "KtOLd1e7CoSXkNxgF7jcDiI7nrd"
WIKI_SPACE_ID = "7612892588537892047"
RD_GROUP = "oc_611b7861968a34f8c2f538f67410b629"  # 研发运维群（实时查询成员）
NOTIFY_GROUP = "oc_8b8978c0510660ec4da3c52ebc7bb9a3"  # 通知群（test测试群）
TARGET_USER = "ou_dfc3579b6b0ced44f7745f24ace77b73"  # 大卫（加急通知）


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


def get_group_members(token, chat_id):
    """实时查询群成员，返回 {member_id: name} 映射"""
    members = {}
    page = ""
    while True:
        url = f"/open-apis/im/v1/chats/{chat_id}/members?page_size=100"
        if page:
            url += f"&page_token={page}"
        resp = feishu_get(token, url)
        for m in resp.get("data", {}).get("items", []):
            members[m.get("member_id", "")] = m.get("name", "")
        if not resp.get("data", {}).get("has_more"):
            break
        page = resp.get("data", {}).get("page_token", "")
    return members


def get_mention_name_map(token):
    """从模板文档获取 mention_user user_id -> 显示名 的映射"""
    raw_url = f"/open-apis/docx/v1/documents/{TEMPLATE_DOC}/raw_content?document_id={TEMPLATE_DOC}"
    resp = feishu_get(token, raw_url)
    raw_content = resp.get("data", {}).get("content", "")
    names = re.findall(r'@([^\s\n]+)', raw_content)

    blocks = []
    page = ""
    while True:
        path = f"/open-apis/docx/v1/documents/{TEMPLATE_DOC}/blocks/{TEMPLATE_DOC}/children?page_size=50"
        if page:
            path += f"&page_token={page}"
        resp = feishu_get(token, path)
        items = resp.get("data", {}).get("items", [])
        blocks.extend(items)
        if not resp["data"].get("has_more"):
            break
        page = resp["data"]["page_token"]

    uids = []
    for b in blocks:
        for field in ("heading1", "heading2", "heading3", "text", "bullet", "ordered"):
            if field in b:
                for el in b[field].get("elements", []):
                    if "mention_user" in el:
                        uids.append(el["mention_user"].get("user_id", ""))

    return dict(zip(uids, names))


def clean_block(block, name_map, group_members):
    """清理 block，移除 block_id、parent_id，替换 mention_user 为 text_run。
    如果用户不在研发运维群中，跳过整个 block（heading3 + 后续空行）。
    """
    bt = block.get("block_type", 0)
    # heading3 包含 mention_user：检查用户是否在群中
    if bt == 5:  # heading3
        elements = block.get("heading3", {}).get("elements", [])
        for el in elements:
            if "mention_user" in el:
                uid = el["mention_user"].get("user_id", "")
                if uid not in group_members:
                    return None  # 跳过不在群中的用户

    clean = {k: v for k, v in block.items() if k not in ("block_id", "parent_id")}
    for key in ("heading1", "heading2", "heading3", "text"):
        if key in clean:
            elements = clean[key].get("elements", [])
            new_elements = []
            for elem in elements:
                if "mention_user" in elem:
                    mention = elem["mention_user"]
                    style = mention.get("text_element_style", {})
                    uid = mention.get("user_id", "")
                    display_name = name_map.get(uid, "用户") if name_map else "用户"
                    new_elements.append(
                        {
                            "text_run": {
                                "content": f"@{display_name}",
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


def create_wiki_node(token, space_id, title):
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


def grant_group_permission(token, doc_id, chat_id):
    """给群开文档编辑权限"""
    resp = feishu_post(
        token,
        f"/open-apis/drive/v1/permissions/{doc_id}/members/batch_create?type=docx",
        {
            "members": [
                {
                    "member_type": "openchat",
                    "member_id": chat_id,
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

    print(f"[1/7] Building mention name map...")
    name_map = get_mention_name_map(token)
    print(f"  Mapped {len(name_map)} users from template")

    print(f"[2/7] Fetching R&D group members (real-time)...")
    group_members = get_group_members(token, RD_GROUP)
    print(f"  Group has {len(group_members)} members")
    in_group = {uid: name for uid, name in name_map.items() if uid in group_members}
    not_in_group = {uid: name for uid, name in name_map.items() if uid not in group_members}
    print(f"  In group: {len(in_group)}, Not in group: {len(not_in_group)}")
    if not_in_group:
        print(f"  Skipped: {', '.join(not_in_group.values())}")

    print(f"[3/7] Creating wiki node...")
    node = create_wiki_node(token, WIKI_SPACE_ID, title)
    doc_id = node["obj_token"]
    wiki_url = node.get("url", "")
    print(f"  Doc ID: {doc_id}")
    print(f"  Wiki URL: {wiki_url}")

    print(f"[4/7] Fetching template blocks...")
    raw_blocks = get_template_blocks(token)
    print(f"  Got {len(raw_blocks)} blocks")

    print(f"[5/7] Cleaning (filter group members) and writing blocks...")
    clean_blocks = [cb for b in raw_blocks if (cb := clean_block(b, name_map, group_members)) is not None]
    write_blocks(token, doc_id, clean_blocks)
    print(f"  Wrote {len(clean_blocks)} blocks (filtered {len(raw_blocks) - len(clean_blocks)})")

    print(f"[6/7] Granting edit permission to R&D group...")
    perm_resp = grant_group_permission(token, doc_id, RD_GROUP)
    print(f"  Permission result: {perm_resp.get('code')} {perm_resp.get('msg')}")

    print(f"[7/7] Sending notification to group...")
    # Build @ list for in-group users using post message type
    at_elements = []
    for uid, name in in_group.items():
        at_elements.append({"tag": "at", "user_id": uid, "text": f"@{name}"})
    at_elements.append({"tag": "text", "text": "\n请各负责人填写本周进展。"})

    content = [
        [{"tag": "text", "text": f"📋 技术周会文档已创建"}],
        [{"tag": "text", "text": f"📅 {week_str}"}],
        [{"tag": "a", "text": f"🔗 {wiki_url}", "href": wiki_url}],
        [{"tag": "text", "text": ""}],  # 空行
        at_elements
    ]

    msg_resp = feishu_post(
        token,
        "/open-apis/im/v1/messages?receive_id_type=chat_id",
        {
            "receive_id": NOTIFY_GROUP,
            "msg_type": "post",
            "content": json.dumps({"zh_cn": {"title": "技术周会文档已创建", "content": content}}),
        },
    )
    if msg_resp.get("code") == 0:
        msg_id = msg_resp["data"]["message_id"]
        feishu_post(
            token,
            f"/open-apis/im/v1/messages/{msg_id}/urgent_app?user_id_type=open_id",
            {"user_id_list": [TARGET_USER]},
            method="PATCH",
        )
        print(f"  Message sent with @mentions + urgent to 大卫")
    else:
        print(f"  Message send failed: {msg_resp}")

    print(f"\nDone! Wiki URL: {wiki_url}")
    return wiki_url


if __name__ == "__main__":
    main()
