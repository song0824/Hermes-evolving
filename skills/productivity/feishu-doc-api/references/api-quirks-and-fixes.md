# Feishu API Quirks and Verified Patterns

## 1. Wiki Node Creation Ignores obj_token (verified 2026-11-02)

When creating a wiki node with `POST /wiki/v2/spaces/{space_id}/nodes`:

```python
# THIS DOES NOT WORK as expected:
resp = api_post(wiki_url, token, {
    "parent_node_token": PARENT_NODE,
    "node_type": "origin",
    "obj_type": "docx",
    "obj_token": MY_DOC_ID,    # ← IGNORED by Feishu API!
    "title": title
})
# Feishu creates its OWN empty document, MY_DOC_ID is orphaned
```

**Result**: Two documents exist:
1. Your doc (MY_DOC_ID) with all content — NOT in wiki tree
2. Feishu's auto-created doc (new obj_token) — EMPTY, in wiki tree

**Correct flow**:
```python
# 1. Create wiki node WITHOUT obj_token
resp = api_post(wiki_url, token, {
    "parent_node_token": PARENT_NODE,
    "node_type": "origin",
    "obj_type": "docx",
    "title": title
})
doc_id = resp["data"]["node"]["obj_token"]  # Get Feishu's auto-generated doc ID

# 2. Write blocks TO THAT doc_id
api_post(f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children", token, {"children": blocks})
```

## 2. mention_user Write API Not Reliable (verified 2026-11-02)

The `mention_user` element in blocks API returns `user_id` but no display name. When writing to a new document:

**Problem**: `mention_user` elements may be silently dropped, causing empty headings.

**Solution**: Use raw_content + blocks combo to build user_id → display_name mapping:

```python
# Fetch raw_content (preserves display names)
raw = api_get(f"/open-apis/docx/v1/documents/{doc}/raw_content?document_id={doc}", token)
names = re.findall(r'@([^\s\n]+)', raw["data"]["content"])

# Fetch blocks (preserves user_ids)
uids = extract_uids_from_blocks(blocks)

# Map them (order preserved in both APIs)
name_map = dict(zip(uids, names))

# Write as text_run with @display_name
{"text_run": {"content": f"@{display_name}"}}
```

## 3. Config Credentials & Git Push (2026-11-02 / 2026-11-09)

When pushing to GitHub, `config.yaml` had:
```yaml
app_id: ${FEISHU_APP_ID}
app_secret: ${FEISHU_APP_SECRET}
```
Instead of real values, causing all Feishu API calls to return `code: 10003, msg: invalid param`.

**Fix**: Restore real values manually:
```yaml
app_id: cli_a97b1e4633f99cb0
app_secret: ${FEISHU_APP_SECRET}
```

**⚠️ GitHub Secret Scanning (2026-11-09)**: Pushing files with hardcoded `app_secret` values to GitHub triggers GH013 push protection — push is rejected. Replace with `${FEISHU_APP_SECRET}` placeholder before committing. Check `skills/.curator_backups/` too — old cron job JSON backups contain secrets embedded in prompt strings and should be excluded from git entirely (add to `.gitignore`).

**⚠️ Secret Scanning (2026-11-09)**: GitHub's push protection **blocks pushes containing hardcoded Feishu `app_secret`**. If `config.yaml` or any skill file contains the plaintext secret (e.g., `3VO3tDBRDAo7pTCgGZViXg7gOo3OBlij`), the push is rejected with `GH013: Push cannot contain secrets — Lark Application Secret`.

**Rule**: Always use `${FEISHU_APP_SECRET}` placeholder in files that will be committed. Replace with actual value only in `~/.hermes/.env`. Also check `skills/.curator_backups/` — old cron job JSON backups contain secrets in prompt strings and should be excluded from `.gitignore`.

## 4. Permission Grant Returns 1063003 (Non-blocking)

`POST /drive/v1/permissions/{DOC_ID}/members/batch_create?type=docx` may return `code: 1063003`. This typically means the user already has permission or the app lacks `docs:permission.member` scope. This does NOT block document viewing/editing — the document is still accessible.
