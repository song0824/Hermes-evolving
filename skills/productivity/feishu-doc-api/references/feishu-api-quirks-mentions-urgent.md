# Feishu API Quirks: @mentions, Urgent App, and Group Resolution

## mention_user in Write API
- Writing `{"mention_user": {"user_id": "ou_xxx"}}` in block elements returns `1770001 "invalid param"`.
- **Workaround**: Write `text_run` with `@{display_name}` (e.g., `@黑洞`). Feishu auto-detects the `@name` pattern and renders it as a clickable mention.
- **Resolution pattern**: Use `raw_content` API to get display names, blocks API to get `user_id`, then `dict(zip(uids, names))`.

## @ Mentions in Group Messages
- `msg_type: "text"` with `<at user_id="ou_xxx">name</at>` does NOT trigger real @ notifications — renders as plain text.
- **Must use `msg_type: "post"`** with structured content:
```json
{
  "zh_cn": {
    "title": "Title",
    "content": [
      [{"tag": "text", "text": "Line 1"}],
      [{"tag": "at", "user_id": "ou_xxx", "text": "@Name"}],
      [{"tag": "text", "text": "Please fill in."}]
    ]
  }
}
```

## urgent_app Cross-App Error (code 99992361)
- `POST /im/v1/messages/{msg_id}/urgent_app` with `open_id` from another app returns `open_id cross app`.
- **Resolution**: The `open_id` must belong to the current app. Use group member list to resolve:
```python
def resolve_urgent_open_id(group_members, configured_open_id, display_name):
    if configured_open_id in group_members:
        return configured_open_id
    # Fallback: match by name
    exact = [uid for uid, name in group_members.items() if name == display_name]
    partial = [uid for uid, name in group_members.items() if display_name in (name or "")]
    chosen = exact or partial
    if len(chosen) == 1:
        return chosen[0]
    raise Exception(f"Cannot resolve {display_name} for urgent_app.")
```
- **Always wrap urgent_app call in try/except** — failure should not block the main job.

## Group Permission Grants
- Use `member_type: "openchat"` with group `chat_id` to grant doc permissions to all members.
- Endpoint: `POST /drive/v1/permissions/{doc_id}/members/batch_create?type=docx`
