# Bitable Parent Items Extraction Pattern

## Parent Items Field Structure

The `Parent items` (parent reference) field in Bitable records returns a complex nested structure. Always handle all three variants:

### Variant 1: Has record_ids and text
```json
{
  "record_ids": ["recvllEODjDIrG"],
  "table_id": "tbl9c4NAOuRuIPpt",
  "text": "Parent Record Name",
  "text_arr": ["Parent Record Name"],
  "type": "text"
}
```
→ Use `text` or `text_arr[0]` for the parent name.

### Variant 2: Has record_ids but no text
```json
{
  "record_ids": ["recvllEODjDIrG"],
  "table_id": "tbl9c4NAOuRuIPpt",
  "text": "",
  "text_arr": [],
  "type": "text"
}
```
→ Use `record_ids[0]` to look up the parent record's name from your records map.

### Variant 3: Empty parent (no record_ids, no text)
```json
{
  "table_id": "tbl9c4NAOuRuIPpt",
  "text_arr": [],
  "type": "text"
}
```
→ This record has no parent. The `record_ids` key is absent.

## Extraction Code

```python
def get_parent_info(parent_raw, name_map):
    if not parent_raw or not isinstance(parent_raw, list) or len(parent_raw) == 0:
        return ""
    p = parent_raw[0]
    if not isinstance(p, dict):
        return ""
    
    # Try text first
    parent_text = p.get("text", "")
    if parent_text:
        return parent_text
    
    # Try text_arr
    text_arr = p.get("text_arr", [])
    if text_arr and len(text_arr) > 0:
        return text_arr[0]
    
    # Try record_ids lookup
    rec_ids = p.get("record_ids", [])
    if rec_ids and rec_ids[0] in name_map:
        return name_map[rec_ids[0]]
    
    # Empty parent
    return ""
```

## Building the Name Map

Before processing Parent items, build a `record_id → name` map from all records:

```python
name_map = {}
for r in all_records:
    rid = r.get("record_id")
    name = r.get("fields", {}).get("Project name", "")
    if rid:
        name_map[rid] = name
```

## Nested Parent Chains

Records can have multi-level parent chains (grandparent → parent → child). To get full context:

```python
# Build chain by repeatedly looking up parent's parent
def get_full_parent_chain(record, name_map, all_records_map, max_depth=5):
    chain = []
    current = record
    for _ in range(max_depth):
        parent_raw = current.get("fields", {}).get("Parent items")
        parent_name = get_parent_info(parent_raw, name_map)
        if not parent_name:
            break
        chain.append(parent_name)
        # Look up parent record for next iteration
        parent_rec_ids = parent_raw[0].get("record_ids", []) if parent_raw else []
        if not parent_rec_ids or parent_rec_ids[0] not in all_records_map:
            break
        current = all_records_map[parent_rec_ids[0]]
    return list(reversed(chain))  # Return from root to immediate parent
```
