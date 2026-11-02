# 飞书文档图片下载技巧

## 下载文档内嵌图片

飞书文档（docx）中的图片不能通过 `im/v1/images/{token}` 下载（返回 code=234001 Invalid request param）。

**正确做法**：使用 drive media download API
```
GET https://open.feishu.cn/open-apis/drive/v1/medias/{image_token}/download
Authorization: Bearer {tenant_access_token}
```

返回的是原始 PNG/JPG 二进制数据。

## 如何获取图片 token

1. 先获取文档 blocks：
   ```
   GET /open-apis/docx/v1/documents/{doc_id}/blocks?page_size=500
   ```

2. 遍历 blocks，图片可能在以下位置：
   - **独立图片 block**（block_type=31）：`block.image.token`
   - **Grid block（type=27）**：图片直接在 block 上 `block.image.token`，**不在 children 里**。Grid 的 children 列表为空，但 block 本身有 image 字段。
   - **嵌套 Grid**：同理，图片在 grid_column.blocks[*] 的顶层 image 字段

3. 每个图片 token 对应一个唯一图片，用 drive API 下载即可。

## Grid block (type=27) 的特殊性

飞书 docx API 中，Grid block 的图片**不作为子 block 存在**，而是直接挂在 block 对象上：
```json
{
  "block_type": 27,
  "block_id": "...",
  "image": {
    "token": "xxx",
    "width": 1536,
    "height": 1024
  },
  "parent_id": "...",
  "grid": { "column_size": 0, "grid_column": [] }
}
```
即使 `grid_column` 为空数组，图片仍然在 `block.image` 上。不要试图 fetch children 来找图片。

## 其他特殊 block 类型

- **type=33**：View block，包含子 block 列表（通过 children 字段关联）
- **type=23**：File block，包含 `{file: {name, token}}`，可通过 wiki/docx API 进一步获取
