# Structured Document Generation Patterns for Feishu

When creating form-like or report documents in Feishu, table blocks (type 18) cannot be created via the write API (error 9499). Use these text-based patterns instead.

## Helper Functions

```python
def T(text, bold=False):
    el = {"text_run": {"content": text}}
    if bold:
        el["text_run"]["text_element_style"] = {"bold": True}
    return {"block_type": 2, "text": {"elements": [el]}}

def Empty():
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}

def CalloutBlock(text, bg=2):
    return {
        "block_type": 19,
        "callout": {
            "elements": [{"text_run": {"content": text}}],
            "background_color": bg,  # 2=blue, 5=green, 6=orange, 8=red
            "emoji_id": "test"
        }
    }

def F(label, value):
    """Field: label + value on same line, label bold"""
    return {"block_type": 2, "text": {"elements": [
        {"text_run": {"content": "  " + label + "：", "text_element_style": {"bold": True}}},
        {"text_run": {"content": value}}
    ]}}

def Bullet(text):
    return {"block_type": 12, "bullet": {"elements": [{"text_run": {"content": text}}]}}

def H1(text):
    return {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": text}}]}}

def H2(text):
    return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": text}}]}}
```

## Layout Pattern

```
H1: Document Title
T: Subtitle (bold)
Empty
CalloutBlock: Brief description (bg=2 blue)
Empty

H2: Section One
Empty
F: Field label + value
F: Field label + value
...
Empty

H2: Section Two
Empty
T: Sub-section title (bold)
Bullet: Item 1
Bullet: Item 2
Empty

...

CalloutBlock: Footer note (bg=5 green)
```

## Design Rules

1. **No dividers** — use `Empty()` blocks for spacing. Dividers make documents look cluttered and harder to fill.
2. **H1 for title, H2 for sections** — H1 type 3 and H2 type 4 work reliably.
3. **F() for key-value pairs** — bold label + value on same line with 2-space indent.
4. **T(bold=True) for sub-section headers** — within a section, use bold text as sub-header.
5. **Bullet for lists** — clean and scannable.
6. **CalloutBlock for intro/outro** — bg=2 (blue) for intro, bg=5 (green) for footer.
7. **Leave blanks for unknown data** — use empty string `""` in F() value, or `"____"` for visual placeholder.

## Read Template First

When user modifies a template document in-place, **always read the current template** via `raw_content` API before generating. Do NOT generate from memory or old structure.

```python
url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{template_doc_id}/raw_content?document_id={template_doc_id}"
resp = api_get(url, token)
content = resp["data"]["content"]
# Parse content lines to understand current template structure
```

This ensures you respect any structural changes, field additions/removals, or formatting updates the user made directly in the document.
