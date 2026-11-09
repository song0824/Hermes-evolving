# Real-Time Group Member Filtering for Doc Copy

## Problem
Template documents contain @mention_user elements for users who may no longer be in the target group. Including them creates unnecessary empty sections in new documents.

## Solution
Before writing blocks, query the target group's current members and filter:

```python
def get_group_members(token, chat_id):
    """实时查询群成员，返回 {member_id: name}"""
    members = {}
    page = ""
    while True:
        url = f"/open-apis/im/v1/chats/{chat_id}/members?page_size=100"
        if page: url += f"&page_token={page}"
        resp = feishu_get(token, url)
        for m in resp.get("data", {}).get("items", []):
            members[m.get("member_id", "")] = m.get("name", "")
        if not resp.get("data", {}).get("has_more"): break
        page = resp.get("data", {}).get("page_token", "")
    return members

# In clean_block(), skip heading3 blocks for users not in group:
def clean_block(block, name_map, group_members):
    bt = block.get("block_type", 0)
    if bt == 5:  # heading3
        elements = block.get("heading3", {}).get("elements", [])
        for el in elements:
            if "mention_user" in el:
                uid = el["mention_user"].get("user_id", "")
                if uid not in group_members:
                    return None  # Skip this block
    # ... rest of clean_block logic
```

## Key Findings (2026-11-02)
- 研发运维群 (`oc_611b7861968a34f8c2f538f67410b629`) has 24 members
- Template has 24 @mentions
- 19 users match, 5 users (开拓者、螺旋、昭昭、晚星、流星) are NOT in the group
- Filtering reduces blocks from 63 → 58 (5 heading3 blocks skipped)
