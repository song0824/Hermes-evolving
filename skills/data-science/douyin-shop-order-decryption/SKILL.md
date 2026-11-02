---
name: douyin-shop-order-decryption
description: 抖店订单敏感信息（手机号/地址）解密流程，含开放平台凭证获取、API 调用、额度管理。
trigger: 用户需要抓取抖店订单、解密收货信息、获取抖店开放平台凭证、批量解密手机号地址
---

## 抖店开放平台凭证获取

### 获取 App Key & App Secret
1. 登录 `https://opendj.doudian.com/`（用**抖店商家主账号**，子账号可能看不到完整信息）
2. 顶部导航 → `应用管理` → 左侧 `我的应用` → 点击应用进入 `应用详情`
3. 页面直接显示 `App Key`；`App Secret` 默认隐藏，点击 `查看` 或 `复制`（部分需手机验证码）
4. ⚠️ `App Secret` **只显示一次**，丢失只能重置（旧 Token 失效）

### 获取 Access Token
| 应用类型 | 获取方式 |
|---|---|
| **自用型应用** | 应用详情页 → `Token管理` → 点击 `获取Token` → 授权后即可看到明文（有效期30天） |
| **工具型/定制型** | 构造授权链接：`https://opendj.doudian.com/oauth/authorize?app_id={AppKey}&scope=order&state=1` → 扫码授权 → 回调地址带 `code` → 用 code 换 Token |

### 开通 API 权限
应用管理 → 权限管理 → 开通：
- `order_searchList`（订单列表查询）
- `order_getTradeCipher`（订单敏感信息解密）

## 订单解密 API 流程

### 接口信息
- **Endpoint**: `POST https://openapi-fxg.jinritemai.com/order/getTradeCipher`
- **功能**: 批量解密订单手机号、详细地址、收货人姓名
- **参数**:
  - `order_ids`: 订单号数组（支持批量，建议每批 20-50 个）
  - `cipher_type`: 1=手机号, 2=详细地址, 3=收货人姓名

### 请求签名
抖店 API 需要 HMAC-SHA256 签名，计算方式：
```
sign = HMAC_SHA256(app_secret, app_key + method + param_str + timestamp)
```
具体参数排序、拼接规则见抖店开放平台文档 `https://opendj.doudian.com/document/path?path=196`

### Python 解密脚本示例
```python
import hashlib
import hmac
import json
import time
import requests

APP_KEY = "your_app_key"
APP_SECRET = "your_app_secret"
ACCESS_TOKEN = "your_access_token"

def build_sign(params):
    sorted_params = dict(sorted(params.items()))
    param_str = "".join(f"{k}{v}" for k, v in sorted_params.items())
    sign_str = APP_SECRET + "app_key" + APP_KEY + "method" + sorted_params["method"] + param_str + "timestamp" + str(sorted_params["timestamp"]) + APP_SECRET
    return hashlib.sha256(sign_str.encode()).hexdigest().upper()

def decrypt_orders(order_ids, cipher_type=1):
    timestamp = int(time.time())
    params = {
        "app_key": APP_KEY,
        "method": "order.getTradeCipher",
        "param_json": json.dumps({"order_ids": order_ids, "cipher_type": cipher_type}),
        "timestamp": timestamp,
        "access_token": ACCESS_TOKEN,
        "v": "2",
        "sign_method": "hmac-sha256",
    }
    # 简化版签名，实际需按抖店文档精确拼接
    # 建议使用官方 SDK: pip install doudian-op-sdk
    params["sign"] = build_sign(params)
    
    resp = requests.post("https://openapi-fxg.jinritemai.com/order/getTradeCipher", json=params)
    return resp.json()

# 批量解密 5000 条订单，每批 20 个
order_ids = ["6952970513802335962", "6926450094285291108", ...]
for i in range(0, len(order_ids), 20):
    batch = order_ids[i:i+20]
    result = decrypt_orders(batch, cipher_type=1)  # 1=手机号
    print(result)
    time.sleep(0.15)  # 控制频率
```

**推荐**: 使用抖店官方 Python SDK `pip install doudian-op-sdk`，自动处理签名和 Token 刷新。

## 解密额度限制

| 账号类型 | 解密额度 | 说明 |
|---|---|---|
| **商家主账号** | 几万~几十万条/天 | 店铺主体账号，权限最大 |
| **子账号/客服号** | 几十~几百条/天（如 290 条） | 默认很低，仅够日常客服查看 |
| **新建应用** | 几百~几千条/天 | 可申请提额 |

### 提额路径
抖店开放平台 → 应用管理 → 权限管理 → 找到 `order_getTradeCipher` → 点击「申请」→ 填写业务场景（建议写「日常发货、售后物流通知」）→ 提交审核（1-3 工作日）

### 降级方案
- 主账号登录抖店后台 → 订单管理 → 导出订单 → 勾选「收货人信息」→ 下载 Excel
- 主账号导出的 Excel 通常手机号和地址是明文（取决于店铺安全设置）

## 抖店后台浏览器登录

### 登录 URL
`https://fxg.jinritemai.com/login/common?channel=zhaoshang`

### 切换到扫码登录
页面默认是手机号登录模式，切换到扫码模式需点击右上角 `.login-switcher--cell` 元素：
```js
document.querySelector('.login-switcher--cell').click();
```
切换后页面显示大二维码（中间带蓝色抖店 Logo），用**抖店 APP** 扫描。

### 刷新二维码
二维码过期后（约 2-5 分钟），重新加载页面即可生成新二维码：
```
browser_navigate → 重新打开登录 URL → 点击 .login-switcher--cell
```

### HttpOnly Cookie 限制
抖店的认证 Cookie（PHPSESSID 等）是 **HttpOnly** 的，无法通过 JS `document.cookie` 注入到 Playwright/浏览器会话中。本地登录后的 Cookie 不能共享给服务器端的自动化会话。

### opencli 不适用抖店
opencli 的 `douyin` adapter 面向 `creator.douyin.com`（创作者平台），**不支持** `fxg.jinritemai.com`（抖店商家后台）。opencli `browser` 模式需要 Chrome Browser Bridge 扩展连接（`opencli doctor` 显示 Extension: connected），但服务器端 daemon 默认监听 `127.0.0.1:19825`，需 SSH 隧道才能让本地扩展连接。

## Cookie 直接调 API（替代方案）

### 已验证可用的 API 端点

| 方法 | URL | 状态 | 说明 |
|------|-----|------|------|
| GET | `/api/order/orderDetail?order_id=XXX` | ✅ 200 JSON | 返回订单详情（手机号/地址已脱敏） |
| POST | `/api/order/list` | ❌ 404 | 不存在 |
| POST | `/ffa/api/order/list` | ❌ HTML | 返回页面而非 API |
| GET/POST | `/api/order/search` | ❌ 404 | 不存在 |
| POST | `/api/order/getTradeCipher` | ❌ 404 | 开放平台端点，不在前端 API |

### 订单详情 API 返回数据结构（已验证）
```json
{
  "errno": 0, "code": 0,
  "data": {
    "order_id": "6952970513802335962",
    "receiver": {
      "post_receiver": "洛*",        // 姓名脱敏
      "post_tel": "1**********",      // 手机号脱敏
      "post_addr": {
        "province": {"name": "广西壮族自治区"},
        "city": {"name": "北海市"},
        "town": {"name": "海城区"},
        "street": {"name": "驿马街道"},
        "detail": "***********"       // 详细地址脱敏
      },
      "can_view": 1,                  // 可点击查看明文（需滑块验证）
      "buyer_tel_info": {"pay_tel": "", "nick_name": "可*"}
    },
    "order_base": {"labels": [...]},
    "product": {"sku": [...]},
    "delivery": {"labels": [...]}
  }
}
```
省市区街道正常返回，仅姓名/手机号/详细地址脱敏。

### 获取 Cookie
在已登录的抖店页面按 F12 → Console → 输入 `document.cookie` → 复制输出。

### 订单详情 API
```
GET https://fxg.jinritemai.com/api/order/orderDetail?order_id={订单号}
Cookie: {复制的cookie}
Referer: https://fxg.jinritemai.com/ffa/morder/order/list
```

返回订单基本信息（订单号、时间、状态、商品），但 **手机号和地址被脱敏**（`1**********`、`***********`）。

### 重要发现
1. 订单详情 API 不触发验证码，直接返回数据
2. 但收货信息字段被服务端脱敏，无法通过此 API 获取明文
3. 查看明文需要在 UI 上点击"查看"→ 滑块验证码 → 通过后才能显示
4. **无法自动化批量获取明文收货信息**

## 最佳实践：批量导出

对于大批量订单（如 5000+）的收货信息获取：

1. 抖店主账号登录后台
2. 订单管理 → 批量导出
3. 选择包含「收货人信息」（姓名、手机号、地址）
4. 下载 Excel 后交给我处理

这是最快、最可靠的方式，无需 API 配额，无需处理验证码。
