# Feishu Docx Block Types — WRITE Mapping (Verified 2026-05-23)

Verified by creating a document and writing blocks via `/docx/v1/documents/{doc_id}/blocks/{doc_id}/children`. Each successful write echoes back the correct `block_type`.

## Confirmed Working Block Types

| block_type | Type | Body Key | Example |
|---|---|---|---|
| 2 | Paragraph | `text` | `{"block_type": 2, "text": {"elements": [...]}}` |
| 3 | Heading 1 | `heading1` | `{"block_type": 3, "heading1": {"elements": [...]}}` |
| 4 | Heading 2 | `heading2` | `{"block_type": 4, "heading2": {"elements": [...]}}` |
| 5 | Heading 3 | `heading3` | `{"block_type": 5, "heading3": {"elements": [...]}}` |
| 12 | Bullet list | `bullet` | `{"block_type": 12, "bullet": {"elements": [...]}}` |
| 13 | Ordered list | `ordered` | `{"block_type": 13, "ordered": {"elements": [...]}}` |

## Known Limitations

- **Divider (block_type 21)**: Returns error `1770029 "block not support to create"`. Workaround: use an empty text block `{"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}` or a text block with `---`.
- **Batch limit**: Maximum 2 blocks per request. Error `1770001` if > 2.
- **Rate limiting**: After ~12 batch requests, returns 429. Retry with 2-3s sleep.

## Previous Wrong Mappings (DO NOT USE)

The following mappings were previously documented as "verified" but are INCORRECT:
- 1=Paragraph, 2=Heading 1, 3=Heading 2, etc. (off-by-one on everything)
- 12=Image (actually 12=Bullet)
- 22=Bullet (actually 12=Bullet)
- 27=Image in grid (actually 23=Image)

## Read vs Write Consistency

The GET API (reading blocks) returns the SAME block_type numbers as the WRITE API uses. So block_type 2 in a GET response = paragraph, block_type 3 = heading1, etc.
