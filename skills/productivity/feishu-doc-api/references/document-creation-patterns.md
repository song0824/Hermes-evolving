# Feishu Document Creation Patterns

## Group Permission Grant (Recommended)

Instead of granting permissions to individual users, grant to the entire group:

```python
resp = feishu_post(token, 
    f"/open-apis/drive/v1/permissions/{doc_id}/members/batch_create?type=docx",
    {"members": [{"member_type": "openchat", "member_id": GROUP_CHAT_ID, "perm": "full_access"}]})
```

This automatically gives all current group members edit access. New members joining the group also get access. Returns code 0 on success.

## Real-time Group Member Filtering

When creating documents from templates that contain `@mention_user` placeholders, query group membership at runtime to filter out users no longer in the group:

```python
def get_group_members(token, chat_id):
    """Query group members via IM API, returns {member_id: name}"""
    members = {}
    page = ""
    while True:
        resp = feishu_get(token, f"/open-apis/im/v1/chats/{chat_id}/members?page_size=100" + 
                          (f"&page_token={page}" if page else ""))
        for m in resp.get("data", {}).get("items", []):
            members[m.get("member_id", "")] = m.get("name", "")
        if not resp.get("data", {}).get("has_more"): break
        page = resp.get("data", {}).get("page_token", "")
    return members
```

During block cleaning, skip heading3 blocks whose mention_user is not in the group:

```python
def clean_block(block, name_map, group_members):
    if block.get("block_type") == 5:  # heading3
        for el in block.get("heading3", {}).get("elements", []):
            if "mention_user" in el:
                uid = el["mention_user"].get("user_id", "")
                if uid not in group_members:
                    return None  # Skip users not in group
    # ... normal cleaning logic ...
```

This ensures the document only contains sections for active group members.

## Real @Mentions in IM Messages

To send a message that actually @mentions users (triggers notification, shows blue clickable name), you MUST use `msg_type: "post"` with structured content. The `msg_type: "text"` approach with `<at user_id="xxx">` does NOT work — it renders as plain text.

```python
# Build at elements for each user to mention
at_elements = []
for uid, name in users_to_mention.items():
    at_elements.append({"tag": "at", "user_id": uid, "text": f"@{name}"})
at_elements.append({"tag": "text", "text": "\nPlease fill in your sections."})

content = [
    [{"tag": "text", "text": "📋 Document created"}],
    [{"tag": "text", "text": "📅 2026-11-02"}],
    [{"tag": "a", "text": "🔗 https://...", "href": "https://..."}],
    [{"tag": "text", "text": ""}],  # blank line
    at_elements
]

resp = feishu_post(token, "/open-apis/im/v1/messages?receive_id_type=chat_id", {
    "receive_id": chat_id,
    "msg_type": "post",
    "content": json.dumps({"zh_cn": {"title": "Document created", "content": content}})
})
```

Each `{"tag": "at", "user_id": "ou_xxx", "text": "@Name"}` element creates a real Feishu @mention that triggers push notifications and shows as a blue clickable name.

### ⚠️ msg_type: "text" does NOT support @mentions

The `<at user_id="ou_xxx">Name</at>` syntax inside a `msg_type: "text"` message renders as **plain text**, not as a real @mention. Users will NOT receive notifications. Always use `msg_type: "post"` with the structured content format above for @mentions.

## mention_user Write Limitation (1770001)

The docx blocks write API (`POST /docx/v1/documents/{id}/blocks/{id}/children`) **rejects `mention_user` elements** with error 1770001 "invalid param". 

**Workaround**: Convert `mention_user` to `text_run` with `@{display_name}`:

```python
# Before writing, transform mention_user elements
for elem in elements:
    if "mention_user" in elem:
        uid = elem["mention_user"]["user_id"]
        display_name = name_map.get(uid, "用户")
        new_elem = {"text_run": {
            "content": f"@{display_name}",
            "text_element_style": elem["mention_user"].get("text_element_style", {})
        }}
```

The display name mapping comes from `raw_content` API which preserves original @mentions. See the main skill for the full raw_content + blocks mapping pattern.

## @username as text_run IS Recognized in Documents

Contrary to initial concern, writing `{"text_run": {"content": "@黑洞"}}` in a document block DOES result in Feishu recognizing it as a real @mention (blue clickable name that triggers notifications). You do NOT need to use `mention_user` elements in documents — the `text_run` approach works and avoids the 1770001 error.

**Verified 2026-11-02**: Document created with `@黑洞`, `@卢腾`, etc. as `text_run.content` — all rendered as real @mentions in the Feishu app.
