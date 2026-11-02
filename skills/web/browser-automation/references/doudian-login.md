# 抖店 (DouDian / jinritemai.com) Login Notes

## Login URL
`https://fxg.jinritemai.com/login/common?channel=zhaoshang`

## QR Code API Endpoints
- **Get QR**: `https://doudian-sso.jinritemai.com/passport/sso/get_qrcode/?fp=<fingerprint>`
- **Check Scan**: `https://doudian-sso.jinritemai.com/passport/sso/check_qrconnect/?fp=<fingerprint>`
  - Response: `{"data":{"status":"1"}, "error_code":0}` → waiting for scan
  - Response: `{"error_code":2046, "description":"为保证账号安全，暂不支持此操作"}` → **security block (headless detected)**
- **Check Login**: `https://doudian-sso.jinritemai.com/passport/sso/check_login/?fp=<fingerprint>`
  - Response: `{"has_login":false}` → not logged in
  - Response: `{"has_login":true}` → logged in
- **Aff Check**: `https://doudian-sso.jinritemai.com/passport/sso/aff/check_login/`
  - Response: `{"subject_has_login":false}` → not logged in

## QR Code Copywriting
The `get_qrcode` response includes a `copywriting` JSON field:
```json
{
  "desc": "为保障账号安全，请使用[color=red]「抖音 APP」[/]扫码验证，以确保为本人操作",
  "page_title": "身份验证",
  "title": "请使用已登录账号的设备扫码"
}
```
**Important**: The QR code may require **抖音 APP** (Douyin), not **抖店 APP** (DouDian). Always read this field to tell the user which app to use.

## Login Page Structure
- Login form uses class `index_loginPage__K_bGK`
- QR code switch button: `.login-switcher--cell`
- Login form section: `.account-center-sdk-container`

## Target Pages (after login)
- Order list: `https://fxg.jinritemai.com/ffa/morder/order/list`
- Dashboard: `https://fxg.jinritemai.com/ffa/homepage`

## Known Cookies (after successful login)
- `sessionid` / `sessionid_ss` / `sid_tt` / `sid_guard` — core session cookies
- `passport_csrf_token` — CSRF protection
- `ttwid` — tracking ID

## Error 2046 Workaround
When `check_qrconnect` returns error 2046:
1. The server has detected headless browser automation
2. Solution: Connect to real Chrome via CDP (`connect_over_cdp`) instead of launching headless Playwright
3. Real Chrome uses the existing user-data-dir with extensions and real browser fingerprint
