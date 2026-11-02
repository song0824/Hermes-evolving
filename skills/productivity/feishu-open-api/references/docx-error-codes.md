# Docx Block Write Error Codes — Reference

## 1770001 "invalid param" — RESOLVED
Root cause: `block_type: 2` uses `"text"` key, NOT `"paragraph"`. See `docx-block-write-failure.md`.

## 1770005 "too deep level" — RESOLVED
Root cause: chaining blocks via last block ID causes nesting. Fix: always use `doc_id` as parent. See SKILL.md.

## 1770032 "forBidden" — mention_user blocks

When writing blocks containing `mention_user` elements to a document, the API returns `1770032 forBidden`. This occurs because the bot app does not have permission to mention those users (the users may not have interacted with the bot, or the app lacks contact permissions).

**Affected block types**: heading1 (3), heading2 (4), heading3 (5), text (2) — any block that can contain `mention_user` elements.

**Fix**: Replace `mention_user` elements with `text_run` before writing. See SKILL.md "mention_user blocks cause 1770032" section for the `clean_block()` function.

**Note**: This is NOT about the bot lacking write permission to the document — it's specifically about the `mention_user` element type. Plain text blocks with the same bot permissions write successfully.

## 99991672 "Access denied" (Contact API)
The bot app lacks `contact:contact.base:readonly` permission. Cannot resolve user names from open_id. Workaround: use `text_run` placeholders instead of resolving user names for mentions.

## Block Type Reference

| block_type | Field Key | Can contain mention_user? |
|---|---|---|
| 1 | `page` | No |
| 2 | `text` | Yes |
| 3 | `heading1` | Yes |
| 4 | `heading2` | Yes |
| 5 | `heading3` | Yes |
