# 飞书文档 API 权限端点速查

## 文档创建
```
POST /docx/v1/documents
Body: {"folder_token": "", "title": "标题"}
返回: data.document.document_id
```

## Block 写入
```
POST /docx/v1/documents/{doc_id}/blocks/{doc_id}/children
Body: {"children": [block1, block2]}
限制: 每次最多 2 个 blocks，批次间 1.5s 延迟
```

## 权限管理
```
# 读取权限设置
GET /drive/v1/permissions/{doc_id}/public?type=docx
返回: permission_public (link_share_entity, comment_entity, external_access 等)

# 给群组开权限
POST /drive/v1/permissions/{doc_id}/members?type=docx
Body: {"member_type": "openchat", "member_id": "oc_xxx", "perm": "full_access"}

# ❌ 以下端点返回 404（无 drive 写权限时）
PATCH /drive/v1/permissions/{doc_id}/link/share/entity?type=docx
PUT  /drive/v1/permissions/{doc_id}/public?type=docx
```

## Block text_run 格式
```json
{"text_run": {"content": "文本内容", "style": {}}}
```
⚠️ 必须用 `content` 字段，不能用 `text`。

## Block 类型
| block_type | 类型 | Body Key |
|---|---|---|
| 1 | Title | `title` |
| 2 | Paragraph | `text` |
| 3 | Heading 1 | `heading1` |
| 4 | Heading 2 | `heading2` |
| 5 | Heading 3 | `heading3` |
| 12 | Bullet | `bullet` |
| 13 | Ordered | `ordered` |

## 文档 URL
通用格式：`https://feishu.cn/doc/{doc_id}`
租户格式：`https://{tenant}.feishu.cn/doc/{doc_id}`
