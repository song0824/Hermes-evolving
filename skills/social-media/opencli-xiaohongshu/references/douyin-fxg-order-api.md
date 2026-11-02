# Douyin Store (抖店/fxg) Order API Details

## Authentication
### Key Auth Cookies
```
sid_tt=<value>           # Primary session token
session_id=<value>       # Session identifier
sessionid_ss=<value>     # Server-side session
sid_guard=<value>        # Guard token with expiry
```
Plus tracking cookies: `s_v_web_id`, `passport_csrf_token`, `PHPSESSID`, `tt_scid`, `ecom_us_lt`

### Cookie Validation
Test: `GET https://fxg.jinritemai.com/api/order/orderDetail?order_id=<any>`
- Valid: JSON with order data
- Expired: `{"code":"10008","msg":"登录信息已失效，请重新登录~","st":10000}`

### Getting Cookies
User runs in DevTools Console on logged-in page: `document.cookie`
**Note**: `sid_tt` etc. are HttpOnly — cannot be set via `document.cookie` from JS; must be set via DevTools Application tab or CDP protocol.

## API Endpoints

### Order Detail
```
GET /api/order/orderDetail?order_id=<id>
```
Response structure:
```json
{
  "errno": 0,
  "data": {
    "order_id": "6952970513802335962",
    "order_base": { "operation_actions": [...], "remark": "", "labels": [...] },
    "receiver": {
      "post_receiver": "洛*",        // MASKED
      "post_tel": "1**********",     // MASKED
      "post_addr": {
        "province": {"name": "广西壮族自治区"},
        "city": {"name": "北海市"},
        "town": {"name": "海城区"},
        "street": {"name": "驿马街道"},
        "detail": "***********"      // MASKED
      },
      "can_view": 1
    },
    "product": { "sku": [...] },
    "delivery": { "labels": [...] }
  }
}
```

### Decryption Required for:
- `post_tel` (phone): `1**********` → needs `order/getTradeCipher` with `cipher_type=1`
- `post_addr.detail` (address): `***********` → needs `cipher_type=2`
- `post_receiver` (name): `洛*` → needs `cipher_type=3`

### Decryption API (Open Platform)
```
POST /api/order/getTradeCipher
Body: {"order_id": "<id>", "cipher_type": 1}
```
- Requires: app_key, app_secret, access_token from op.jinritemai.com
- Quota: ~290/day (sub-account), 10k-200k+/day (main account after approval)

## Login URL
```
https://fxg.jinritemai.com/login/common?channel=zhaoshang
```
- Element `.login-switcher--cell` (top-right of login card) switches to QR mode
- QR codes expire in ~2-5 minutes
- User must scan with **抖店 APP** (not standard Douyin app)

## Plain-Text Export Options
1. **Open Platform API** — requires app credentials, quota management
2. **明文导出权限** — apply in backend: 店铺 → 权限管理 → 订单导出明文权限
3. **Third-party ERP** — 风火递, 聚水潭 etc. already have decryption access
