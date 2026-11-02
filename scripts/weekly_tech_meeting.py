#!/usr/bin/env python3
"""
技术周会文档自动复制脚本
每周五 9:00 运行，从模板复制文档到 wiki 空间并通知群
"""
import copy
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
WIKI_PARENT_NODE = "AAGlw95lZi4sUqk78vzc7mkHnIb"  # 技术周会知识库父节点
RD_GROUP = "oc_611b7861968a34f8c2f538f67410b629"  # 研发运维群（实时查询成员）
NOTIFY_GROUP = "oc_8b8978c0510660ec4da3c52ebc7bb9a3"  # 通知群（test测试群）
TARGET_USER = "ou_dfc3579b6b0ced44f7745f24ace77b73"  # 大卫（加急通知）
WIKI_BASE = "https://ta1mz8n1mps.feishu.cn/wiki"
CONTENT_FIELDS = ("heading1", "heading2", "heading3", "text", "bullet", "ordered")
# block_type 3–11 是各级标题。跳过不在群里的人时，连同其小节正文一起丢掉，直到下一个标题。
HEADING_BLOCK_TYPES = range(3, 12)


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
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if resp.get("code") != 0 or not resp.get("tenant_access_token"):
        raise Exception(f"Get tenant_access_token failed: {resp}")
    return resp["tenant_access_token"]


def feishu_request(token, method, path, body_dict=None):
    headers = {"Authorization": f"Bearer {token}"}
    body = None
    if body_dict is not None:
        body = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    conn = http.client.HTTPSConnection("open.feishu.cn", timeout=30)
    try:
        conn.request(method, path, body, headers=headers)
        raw = conn.getresponse().read().decode("utf-8")
    finally:
        conn.close()
    return json.loads(raw)


def feishu_post(token, path, body_dict, method="POST"):
    return feishu_request(token, method, path, body_dict)


def feishu_get(token, path):
    return feishu_request(token, "GET", path)


def get_group_members(token, chat_id):
    """实时查询群成员，返回 {member_id: name}。失败或空名单时中止，避免写成一份没有人的周报。"""
    members = {}
    page = ""
    while True:
        url = f"/open-apis/im/v1/chats/{chat_id}/members?member_id_type=open_id&page_size=100"
        if page:
            url += f"&page_token={page}"
        resp = feishu_get(token, url)
        if resp.get("code") != 0:
            raise Exception(f"List group members failed: {resp}")
        data = resp.get("data") or {}
        for m in data.get("items") or []:
            member_id = m.get("member_id") or ""
            if member_id:
                members[member_id] = m.get("name") or ""
        if not data.get("has_more"):
            break
        page = data.get("page_token") or ""
        if not page:
            raise Exception("List group members returned has_more without page_token")
    if not members:
        raise Exception("R&D group member list is empty, abort before creating a document")
    return members


def mention_user_ids(block):
    uids = []
    for field in CONTENT_FIELDS:
        if field not in block:
            continue
        for el in block[field].get("elements", []):
            if "mention_user" in el:
                uids.append(el["mention_user"].get("user_id", ""))
    return uids


def clean_block(block):
    """去掉 block_id、parent_id，mention 只保留 user_id。"""
    clean = copy.deepcopy(block)
    clean.pop("block_id", None)
    clean.pop("parent_id", None)
    for key in CONTENT_FIELDS:
        if key not in clean:
            continue
        new_elements = []
        for elem in clean[key].get("elements", []):
            if "mention_user" in elem:
                uid = elem["mention_user"].get("user_id", "")
                new_elements.append({"mention_user": {"user_id": uid}})
            else:
                new_elements.append(elem)
        clean[key]["elements"] = new_elements
    return clean


def filter_member_blocks(raw_blocks, group_members):
    """不在研发运维群的 H3 人员，连同该小节直到下一个标题的正文一起丢掉。"""
    kept = []
    skipped = []
    skipping = False
    for block in raw_blocks:
        if skipping:
            if block.get("block_type") in HEADING_BLOCK_TYPES:
                skipping = False
            else:
                continue
        uids = mention_user_ids(block) if block.get("block_type") == 5 else []
        if uids and any(uid not in group_members for uid in uids):
            skipped.extend(uid for uid in uids if uid)
            skipping = True
            continue
        kept.append(clean_block(block))
    person_count = sum(
        1 for block in kept if block.get("block_type") == 5 and mention_user_ids(block)
    )
    return kept, skipped, person_count


def mention_to_text(mention, names):
    uid = mention.get("user_id", "")
    text_run = {"content": f"@{names.get(uid) or '用户'}"}
    style = mention.get("text_element_style")
    if style:
        text_run["text_element_style"] = style
    return {"text_run": text_run}


def downgrade_mentions(block, uids, names):
    """只把指定 user_id 的芯片改成 @名字 文本，其余 mention 保持不变。"""
    clean = copy.deepcopy(block)
    drop = set(uids)
    for key in CONTENT_FIELDS:
        if key not in clean:
            continue
        new_elements = []
        for elem in clean[key].get("elements", []):
            mention = elem.get("mention_user")
            if mention is not None and mention.get("user_id", "") in drop:
                new_elements.append(mention_to_text(mention, names))
            else:
                new_elements.append(elem)
        clean[key]["elements"] = new_elements
    return clean


def get_doc_children(token, doc_id):
    all_blocks = []
    page_token = ""
    while True:
        path = f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=50"
        if page_token:
            path += f"&page_token={page_token}"
        resp = feishu_get(token, path)
        if resp.get("code") != 0:
            raise Exception(f"Get document children failed: {resp}")
        data = resp.get("data") or {}
        all_blocks.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
        if not page_token:
            raise Exception("Get document children returned has_more without page_token")
    return all_blocks


def get_template_blocks(token):
    return get_doc_children(token, TEMPLATE_DOC)


def post_children(token, doc_id, children):
    return feishu_post(
        token,
        f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
        {"children": children},
    )


def write_block_fallback(token, doc_id, block, names):
    """批次因 1770032 失败后，逐个用户把芯片降级成文本再写。"""
    dropped = []
    current = block
    while True:
        resp = post_children(token, doc_id, [current])
        if resp.get("code") == 0:
            return dropped
        if resp.get("code") != 1770032:
            raise Exception(
                f"Write block failed: code={resp.get('code')} msg={resp.get('msg')} "
                f"mention_user={mention_user_ids(current)}"
            )
        remaining = [uid for uid in mention_user_ids(current) if uid not in dropped]
        if not remaining:
            raise Exception(
                f"1770032 remains after downgrading every mention: {resp}"
            )
        victim = remaining[0]
        dropped.append(victim)
        current = downgrade_mentions(block, dropped, names)
        print(f"  Downgraded {victim} ({names.get(victim) or '用户'}) to text")


def write_blocks(token, doc_id, blocks, names):
    downgraded = []
    batch_size = 30
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i : i + batch_size]
        resp = post_children(token, doc_id, batch)
        if resp.get("code") == 1770032:
            print(f"  Batch {i} hit 1770032, retrying one block at a time")
            for block in batch:
                downgraded.extend(write_block_fallback(token, doc_id, block, names))
                time.sleep(0.3)
        elif resp.get("code") != 0:
            raise Exception(
                f"Write blocks batch {i} failed: code={resp.get('code')} "
                f"msg={resp.get('msg')}"
            )
        time.sleep(0.5)
    return downgraded


def list_wiki_children(token, space_id, parent_node_token):
    items = []
    page = ""
    while True:
        path = (
            f"/open-apis/wiki/v2/spaces/{space_id}/nodes"
            f"?parent_node_token={parent_node_token}&page_size=50"
        )
        if page:
            path += f"&page_token={page}"
        resp = feishu_get(token, path)
        if resp.get("code") != 0:
            raise Exception(f"List wiki children failed: {resp}")
        data = resp.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page = data.get("page_token") or ""
        if not page:
            raise Exception("List wiki children returned has_more without page_token")
    return items


def delete_wiki_node(token, space_id, node_token):
    resp = feishu_request(
        token,
        "DELETE",
        f"/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}",
    )
    if resp.get("code") != 0:
        raise Exception(f"Delete wiki node failed: {resp}")
    return resp


def create_wiki_node(token, space_id, title):
    resp = feishu_post(
        token,
        f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
        {
            "parent_node_token": WIKI_PARENT_NODE,
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


def wiki_url_from_node(node):
    wiki_url = node.get("url") or ""
    if wiki_url:
        return wiki_url
    node_token = node.get("node_token", "")
    if not node_token:
        raise Exception(f"Wiki node missing url and node_token: {node}")
    return f"{WIKI_BASE}/{node_token}"


def discard_node(token, node_token):
    try:
        delete_wiki_node(token, WIKI_SPACE_ID, node_token)
        print(f"  Deleted wiki node {node_token}")
    except Exception as exc:
        print(f"  Failed to delete wiki node {node_token}: {exc}")


def prepare_doc_node(token, title, block_count):
    """同一天已有同名文档则复用；写了一半的删掉重建。返回 (node, created)。"""
    existing = [
        node
        for node in list_wiki_children(token, WIKI_SPACE_ID, WIKI_PARENT_NODE)
        if node.get("title") == title
    ]
    if not existing:
        print("  Creating wiki node...")
        return create_wiki_node(token, WIKI_SPACE_ID, title), True

    node = existing[0]
    if len(existing) > 1:
        print(f"  {len(existing)} nodes titled {title}, reusing the first")
    else:
        print(f"  Reusing existing node {node.get('node_token')}")
    children = get_doc_children(token, node["obj_token"])
    if 0 < len(children) < block_count:
        print(
            f"  Partial document ({len(children)}/{block_count} blocks), "
            "deleting and recreating"
        )
        delete_wiki_node(token, WIKI_SPACE_ID, node["node_token"])
        return create_wiki_node(token, WIKI_SPACE_ID, title), True
    return node, False


def main():
    token = get_token()
    week_str = datetime.now().strftime("%Y-%m-%d")
    title = f"技术周会 {week_str}"

    print("[1/6] Fetching R&D group members (real-time)...")
    group_members = get_group_members(token, RD_GROUP)
    print(f"  Group has {len(group_members)} members")

    print("[2/6] Fetching template and filtering members...")
    raw_blocks = get_template_blocks(token)
    clean_blocks, skipped, person_count = filter_member_blocks(raw_blocks, group_members)
    print(f"  Template blocks: {len(raw_blocks)}")
    if skipped:
        print(f"  Skipped sections: {', '.join(skipped)}")
    if person_count == 0:
        raise Exception(
            "No in-group person sections left after filtering, abort before creating a document"
        )
    print(f"  Person sections: {person_count}, blocks to write: {len(clean_blocks)}")

    print("[3/6] Resolving wiki node...")
    node, created = prepare_doc_node(token, title, len(clean_blocks))
    doc_id = node["obj_token"]
    node_token = node.get("node_token") or ""
    wiki_url = wiki_url_from_node(node)
    print(f"  Doc ID: {doc_id}")
    print(f"  Wiki URL: {wiki_url}")

    print("[4/6] Writing blocks...")
    started_write = False
    try:
        children = get_doc_children(token, doc_id)
        if len(children) >= len(clean_blocks):
            print(f"  Document already has {len(children)} blocks, skip write")
            downgraded = []
        else:
            started_write = True
            downgraded = write_blocks(token, doc_id, clean_blocks, group_members)
    except Exception:
        if started_write or created:
            print("  Write failed, deleting this wiki node so a retry will not keep a partial doc")
            if node_token:
                discard_node(token, node_token)
        raise
    if started_write:
        print(f"  Wrote {len(clean_blocks)} blocks")
        if downgraded:
            print(f"  Downgraded mentions: {', '.join(downgraded)}")

    print("[5/6] Granting edit permission to R&D group and notify group...")
    for chat_id, label in ((RD_GROUP, "R&D"), (NOTIFY_GROUP, "notify")):
        perm_resp = grant_group_permission(token, doc_id, chat_id)
        if perm_resp.get("code") != 0:
            raise Exception(f"Grant {label} permission failed: {perm_resp}")
        print(f"  {label} permission ok")

    print("[6/6] Sending notification to group...")
    msg = f"技术周会文档已创建，请大家填写本周周报。\n文档链接：{wiki_url}"
    msg_resp = send_group_message(token, NOTIFY_GROUP, msg)
    if msg_resp.get("code") != 0:
        raise Exception(f"Send message failed: {msg_resp}")
    msg_id = msg_resp["data"]["message_id"]
    urgent_resp = feishu_post(
        token,
        f"/open-apis/im/v1/messages/{msg_id}/urgent_app?user_id_type=open_id",
        {"user_id_list": [TARGET_USER]},
        method="PATCH",
    )
    if urgent_resp.get("code") != 0:
        raise Exception(f"Urgent notify failed: {urgent_resp}")
    print("  Message sent and urgent delivered to 大卫")

    print(f"\nDone! Wiki URL: {wiki_url}")
    return wiki_url


if __name__ == "__main__":
    main()
