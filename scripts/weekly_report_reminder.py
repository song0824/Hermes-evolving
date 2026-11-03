#!/usr/bin/env python3
"""
技术周会周报催填脚本
每周一 11:00 运行：读取知识库最新周报，@ 未填写的人
"""
import argparse
import http.client
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime

from job_lock import acquire_job_lock, release_job_lock

import yaml

CONFIG_PATH = os.path.expanduser("~/.hermes/config.yaml")
WIKI_PARENT_NODE = "AAGlw95lZi4sUqk78vzc7mkHnIb"
OPS_GROUP = "oc_611b7861968a34f8c2f538f67410b629"  # 研发运维群


def log(message: str) -> None:
    print(message, file=sys.stderr)


def notify_chat_id(notify_chat: str = "") -> str:
    return notify_chat.strip() or OPS_GROUP


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notify-chat", default="")
    return parser.parse_args(argv)
WIKI_BASE = "https://ta1mz8n1mps.feishu.cn/wiki"
# 模板提示整行出现时不算已填写。用户自己写的「无」仍然算已填写。
PLACEHOLDER_LINES = {
    "请填写",
    "请填写本周工作",
    "请填写本周进展",
    "请填写本周工作进展",
    "请在此填写",
    "请在此填写本周工作",
    "在此填写",
    "在此填写本周工作",
    "待填写",
    "（请填写）",
    "(请填写)",
    "（待填写）",
    "(待填写)",
}
SECTION_END_MARKERS = ("本周整体", "本周工作进展")
RECENT_DOC_DAYS = 7

CHINA_HOLIDAYS = {
    "2025-01-01",
    "2025-01-02",
    "2025-01-03",
    "2025-01-28",
    "2025-01-29",
    "2025-01-30",
    "2025-01-31",
    "2025-02-01",
    "2025-02-02",
    "2025-02-03",
    "2025-02-04",
    "2025-04-04",
    "2025-04-05",
    "2025-04-06",
    "2025-05-01",
    "2025-05-02",
    "2025-05-03",
    "2025-05-04",
    "2025-05-05",
    "2025-05-31",
    "2025-06-01",
    "2025-06-02",
    "2025-10-01",
    "2025-10-02",
    "2025-10-03",
    "2025-10-04",
    "2025-10-05",
    "2025-10-06",
    "2025-10-07",
    "2025-10-08",
    "2026-01-01",
    "2026-01-02",
    "2026-01-03",
    "2026-02-14",
    "2026-02-15",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-02-19",
    "2026-02-20",
    "2026-02-21",
    "2026-02-22",
    "2026-04-05",
    "2026-04-06",
    "2026-04-07",
    "2026-05-01",
    "2026-05-02",
    "2026-05-03",
    "2026-05-04",
    "2026-05-05",
    "2026-06-19",
    "2026-06-20",
    "2026-06-21",
    "2026-09-25",
    "2026-09-26",
    "2026-09-27",
    "2026-10-01",
    "2026-10-02",
    "2026-10-03",
    "2026-10-04",
    "2026-10-05",
    "2026-10-06",
    "2026-10-07",
    "2027-01-01",
    "2027-01-02",
    "2027-01-03",
    "2027-02-05",
    "2027-02-06",
    "2027-02-07",
    "2027-02-08",
    "2027-02-09",
    "2027-02-10",
    "2027-02-11",
    "2027-04-05",
    "2027-04-06",
    "2027-04-07",
    "2027-05-01",
    "2027-05-02",
    "2027-05-03",
    "2027-05-04",
    "2027-05-05",
    "2027-06-14",
    "2027-06-15",
    "2027-06-16",
    "2027-09-18",
    "2027-09-19",
    "2027-09-20",
    "2027-10-01",
    "2027-10-02",
    "2027-10-03",
    "2027-10-04",
    "2027-10-05",
    "2027-10-06",
    "2027-10-07",
}


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
    conn = http.client.HTTPSConnection("open.feishu.cn", timeout=30)
    body = None
    headers = {"Authorization": f"Bearer {token}"}
    if body_dict is not None:
        body = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    try:
        conn.request(method, path, body, headers=headers)
        raw = conn.getresponse().read().decode("utf-8")
    finally:
        conn.close()
    return json.loads(raw)


def extract_date_from_title(title):
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", title or "")
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", title or "")
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return "0000-00-00"


def display_name(raw_name):
    name = (raw_name or "").lstrip("@").strip()
    if "|" in name:
        name = name.split("|", 1)[0].strip()
    return name


def is_placeholder_line(line):
    text = (line or "").strip()
    if not text:
        return True
    if text in PLACEHOLDER_LINES:
        return True
    wrapped = re.fullmatch(r"[（(]([^）)]{0,40})[）)]", text)
    if wrapped and ("请填写" in wrapped.group(1) or "待填写" in wrapped.group(1)):
        return True
    return False


def leading_mention_names(line):
    """行首连续的 @名字 是标题提及，后面的文字算这一节的正文。"""
    names = []
    rest = []
    started_rest = False
    for part in (line or "").strip().split():
        if not started_rest and part.startswith("@") and part != "@":
            names.append(display_name(part))
        else:
            started_rest = True
            rest.append(part)
    return names, " ".join(rest).strip()


def section_has_content(inline_rest, body_lines):
    if inline_rest and not is_placeholder_line(inline_rest):
        return True
    return any(not is_placeholder_line(line) for line in body_lines)


def h3_uid_groups(blocks):
    groups = []
    for item in blocks:
        if item.get("block_type") != 5:
            continue
        uids = []
        for el in item.get("heading3", {}).get("elements", []):
            mention = el.get("mention_user")
            if not mention:
                continue
            uid = mention.get("user_id", "")
            if uid:
                uids.append(uid)
        if uids:
            groups.append(uids)
    return groups


def align_people(lines, uid_groups):
    """按文档顺序把每个 H3 的 user_id 和同一标题行的显示名配成一对。

    行首 @ 的个数必须等于该 H3 的芯片数。对不齐就失败，不发送催填。
    """
    if not uid_groups:
        raise Exception("周报里没有 H3 mention_user，停止催填")

    people = []
    cursor = 0
    for uids in uid_groups:
        found_at = None
        names = []
        inline = ""
        while cursor < len(lines):
            stripped = lines[cursor].strip()
            if stripped.startswith("@"):
                names, inline = leading_mention_names(stripped)
                if len(names) != len(uids):
                    raise Exception(
                        "无法把 H3 mention 和标题行对齐："
                        f"期望 {len(uids)} 个 @，第 {cursor + 1} 行是 {stripped!r}。"
                        "停止催填，避免 @ 错人"
                    )
                found_at = cursor
                break
            cursor += 1
        if found_at is None:
            raise Exception("raw_content 里的 @ 标题少于 H3 mention，停止催填")

        end = len(lines)
        for index in range(found_at + 1, len(lines)):
            stripped = lines[index].strip()
            if stripped.startswith("@") or any(marker in stripped for marker in SECTION_END_MARKERS):
                end = index
                break
        filled = section_has_content(inline, lines[found_at + 1 : end])
        for uid, name in zip(uids, names):
            people.append((uid, name, filled))
        cursor = end

    for index in range(cursor, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("@"):
            raise Exception(
                f"还有未配对的 @ 行：第 {index + 1} 行 {stripped!r}。停止催填，避免 @ 错人"
            )
    return people


def list_weekly_docs(items, today):
    """标题含「技术周会」、日期在今天及之前 7 天内的全部文档。

    同一周里机器人可能建出多份。这里先全部留下，再按实际填写人数选择。
    """
    candidates = []
    for index, item in enumerate(items):
        title = item.get("title") or ""
        if "技术周会" not in title:
            continue
        iso = extract_date_from_title(title)
        if iso == "0000-00-00":
            continue
        try:
            doc_day = datetime.strptime(iso, "%Y-%m-%d").date()
        except ValueError:
            continue
        age = (today - doc_day).days
        if 0 <= age <= RECENT_DOC_DAYS:
            candidates.append((doc_day, index, item))
    if not candidates:
        raise Exception(
            "最近 7 天内没有标题包含「技术周会」且带日期的周报，停止催填"
        )
    return candidates


def node_created_at(item, fallback):
    for key in ("obj_create_time", "node_create_time"):
        raw = item.get(key)
        if raw in (None, ""):
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return fallback


def pick_weekly_report(loaded):
    """填写人数多的优先。都没人写时用较新的一份，避免催一张已经弃用的空文档。"""
    if not loaded:
        raise Exception("最近 7 天内的周报都无法读取，停止催填")

    def rank(record):
        filled = record["filled_count"]
        created = record["created_at"]
        if filled:
            return (-filled, created)
        return (0, -created)

    return sorted(loaded, key=rank)[0]


def get_wiki_children(token, space_id, parent_node_token):
    items = []
    page = ""
    while True:
        path = (
            f"/open-apis/wiki/v2/spaces/{space_id}/nodes"
            f"?parent_node_token={parent_node_token}&page_size=50"
        )
        if page:
            path += f"&page_token={page}"
        resp = feishu_request(token, "GET", path)
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


def get_raw_content(token, doc_id):
    path = f"/open-apis/docx/v1/documents/{doc_id}/raw_content?document_id={doc_id}"
    resp = feishu_request(token, "GET", path)
    if resp.get("code") != 0:
        raise Exception(f"Read raw_content failed for {doc_id}: {resp}")
    content = (resp.get("data") or {}).get("content")
    if not content:
        raise Exception(f"Weekly report {doc_id} has no raw_content, stop instead of falling back")
    return content


def get_all_blocks(token, doc_id):
    items = []
    page = ""
    while True:
        path = f"/open-apis/docx/v1/documents/{doc_id}/blocks?document_id={doc_id}&page_size=500"
        if page:
            path += f"&page_token={page}"
        resp = feishu_request(token, "GET", path)
        if resp.get("code") != 0:
            raise Exception(f"Get blocks failed: {resp}")
        data = resp.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page = data.get("page_token") or ""
        if not page:
            raise Exception("Get blocks returned has_more without page_token")
    return items


def load_weekly_report(token, doc_day, index, item):
    content = get_raw_content(token, item["obj_token"])
    people = align_people(content.split("\n"), h3_uid_groups(get_all_blocks(token, item["obj_token"])))
    filled_count = sum(1 for _uid, _name, is_filled in people if is_filled)
    return {
        "doc_day": doc_day,
        "created_at": node_created_at(item, index),
        "item": item,
        "content": content,
        "people": people,
        "filled_count": filled_count,
    }


def find_latest_doc(token, today=None):
    node_resp = feishu_request(
        token,
        "GET",
        f"/open-apis/wiki/v2/spaces/get_node?obj_type=wiki&token={WIKI_PARENT_NODE}",
    )
    if node_resp.get("code") != 0:
        raise Exception(f"Resolve wiki parent failed: {node_resp}")
    space_id = node_resp["data"]["node"]["space_id"]
    parent_token = node_resp["data"]["node"]["node_token"]
    items = get_wiki_children(token, space_id, parent_token)
    candidates = list_weekly_docs(items, today or date.today())
    loaded = []
    errors = []
    for doc_day, index, item in candidates:
        title = item.get("title") or item.get("obj_token")
        try:
            record = load_weekly_report(token, doc_day, index, item)
        except Exception as exc:
            errors.append(f"{title}: {exc}")
            log(f"  Skip unreadable: {title}: {exc}")
            continue
        loaded.append(record)
        log(f"  Candidate {title}: filled {record['filled_count']}")
    if not loaded:
        detail = "; ".join(errors) if errors else "no readable document"
        raise Exception(f"最近 7 天内的周报都无法读取，停止催填: {detail}")
    chosen = pick_weekly_report(loaded)
    if len(loaded) > 1:
        log(
            f"  Using {chosen['item'].get('title')} "
            f"(filled {chosen['filled_count']} of {len(loaded)} docs in the last 7 days)"
        )
    return chosen["item"], chosen["content"], chosen["people"]


def run_reminder(notify_chat: str = "") -> None:
    if date.today().isoformat() in CHINA_HOLIDAYS:
        print("SKIP|今天是法定节假日，不发送催填消息")
        return

    token = get_token()
    log("[1/4] Locating this week's report...")
    item, _content, people = find_latest_doc(token)
    doc_title = item.get("title", "")
    doc_url = f"{WIKI_BASE}/{item['node_token']}"
    log(f"  Title: {doc_title}")
    log(f"  Date: {extract_date_from_title(doc_title)}")
    log(f"  URL: {doc_url}")

    log("[2/4] Reading mentions and fill status...")
    filled = [(uid, name) for uid, name, is_filled in people if is_filled]
    unfilled = [(uid, name) for uid, name, is_filled in people if not is_filled]

    log(f"  Filled ({len(filled)}): {', '.join(n for _, n in filled)}")
    log(f"  Unfilled ({len(unfilled)}): {', '.join(n for _, n in unfilled)}")

    if not unfilled:
        print("本周周报都已填写，没有发送催填")
        return

    log("[3/4] Sending reminder...")
    at_tags = "".join(f'<at user_id="{uid}">{name}</at>' for uid, name in unfilled)
    filled_names = ", ".join(n for _, n in filled) or "无"
    message_text = (
        f"{at_tags}\n\n"
        f"技术周会周报催填\n\n"
        f"还有 {len(unfilled)} 位同学未填写周报，请尽快补充。\n\n"
        f"文档链接：{doc_url}\n\n"
        f"已填写（{len(filled)}人）：{filled_names}"
    )
    resp = feishu_request(
        token,
        "POST",
        "/open-apis/im/v1/messages?receive_id_type=chat_id",
        {
            "receive_id": notify_chat_id(notify_chat),
            "msg_type": "text",
            "content": json.dumps({"text": message_text}),
        },
    )
    if resp.get("code") != 0:
        log(f"Send reminder failed: code={resp.get('code')} msg={resp.get('msg')}")
        print("催填消息发送失败，通知没有改发到其他群。")
        sys.exit(1)
    log(f"  Message id: {resp['data']['message_id']}")
    print(f"已催填{len(unfilled)}人")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    lock = acquire_job_lock("weekly_report_reminder")
    if lock is None:
        print("SKIP|上一次催填还在执行，本次没有再跑")
        return
    try:
        run_reminder(args.notify_chat)
    finally:
        release_job_lock(lock)


if __name__ == "__main__":
    main()
